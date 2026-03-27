"""Threshold Engine component - Layer 4: RCE (Response Control & Evaluation)."""

import logging
from typing import Dict, List, Any, Optional

from ..utils.config import ThresholdConfig, InterventionsConfig
from ..models import Contradiction, Intervention, InterventionType, InterventionPriority
from .coherence_monitor import CoherenceMetrics
from ..metrics import get_metrics_exporter

logger = logging.getLogger(__name__)


class ThresholdEngine:
    """
    Layer 4: Response Control & Evaluation (RCE)
    
    Responsibilities:
    - Evaluate triggers against thresholds
    - Decide intervention type and priority
    - Manage intervention escalation
    """
    
    # Domain-specific threshold overrides
    DOMAIN_THRESHOLDS = {
        "finance": {
            "drift_warning": 0.50,
            "rupture_alert": 0.70,
            "drift_velocity": 0.08,
            "recoverability": 0.45
        },
        "politics": {
            "drift_warning": 0.55,
            "rupture_alert": 0.75,
            "drift_velocity": 0.12,
            "recoverability": 0.40
        },
        "medical": {
            "drift_warning": 0.50,
            "rupture_alert": 0.70,
            "drift_velocity": 0.08,
            "recoverability": 0.50
        }
    }
    
    def __init__(
        self,
        thresholds: ThresholdConfig,
        mode: str = "adaptive",
        interventions_config: Optional[InterventionsConfig] = None
    ):
        self.thresholds = thresholds
        self.mode = mode
        self.interventions_config = interventions_config or InterventionsConfig()
        
        # Track intervention counts per session
        self._session_intervention_counts: Dict[str, int] = {}
    
    def update_config(
        self,
        thresholds: ThresholdConfig,
        mode: str
    ) -> None:
        """Update configuration (hot reload support)."""
        self.thresholds = thresholds
        self.mode = mode
    
    def evaluate(
        self,
        metrics: CoherenceMetrics,
        contradictions: List[Contradiction],
        domain: str = "general"
    ) -> Optional[Intervention]:
        """
        Evaluate metrics and determine if intervention is needed.
        
        Args:
            metrics: Calculated coherence metrics
            contradictions: List of detected contradictions
            domain: Conversation domain
            
        Returns:
            Intervention if triggered, None otherwise
        """
        # Get domain-specific thresholds
        thresholds = self._get_thresholds_for_domain(domain)
        
        # Check all trigger conditions
        triggers = []
        
        # 1. Drift warning
        if metrics.delta_g > thresholds["drift_warning"]:
            triggers.append((
                InterventionPriority.MEDIUM,
                f"drift_warning (ΔG={metrics.delta_g:.3f} > {thresholds['drift_warning']})"
            ))
        
        # 2. Rupture alert
        if metrics.delta_g > thresholds["rupture_alert"]:
            triggers.append((
                InterventionPriority.CRITICAL,
                f"rupture_alert (ΔG={metrics.delta_g:.3f} > {thresholds['rupture_alert']})"
            ))
        
        # 3. Accelerating drift
        if metrics.drift_velocity > thresholds["drift_velocity"]:
            triggers.append((
                InterventionPriority.HIGH,
                f"accelerating_drift (Vd={metrics.drift_velocity:.3f} > {thresholds['drift_velocity']})"
            ))
        
        # 4. Variance collapse
        if metrics.variance < self.thresholds.variance_collapse:
            triggers.append((
                InterventionPriority.MEDIUM,
                f"variance_collapse (σ²={metrics.variance:.4f} < {self.thresholds.variance_collapse})"
            ))
        
        # 5. Low recoverability
        if metrics.continuity_score < thresholds["recoverability"]:
            triggers.append((
                InterventionPriority.HIGH,
                f"low_recoverability (CS={metrics.continuity_score:.3f} < {thresholds['recoverability']})"
            ))
        
        # 6. Contradictions
        if contradictions:
            high_confidence_contradictions = [
                c for c in contradictions if c.confidence > 0.8
            ]
            if high_confidence_contradictions:
                triggers.append((
                    InterventionPriority.HIGH,
                    f"contradiction_detected (count={len(high_confidence_contradictions)})"
                ))
            else:
                triggers.append((
                    InterventionPriority.MEDIUM,
                    f"possible_contradiction (count={len(contradictions)})"
                ))
        
        # No triggers - no intervention
        if not triggers:
            return None
        
        # Sort by priority and get highest
        triggers.sort(key=lambda x: x[0].value, reverse=True)
        highest_priority, reason = triggers[0]
        
        # Determine intervention type based on mode and priority
        intervention = self._create_intervention(
            priority=highest_priority,
            reason=reason,
            metrics=metrics,
            all_triggers=triggers
        )
        
        if intervention:
            logger.info(
                f"Intervention triggered: {intervention.type.value} "
                f"({intervention.reason})"
            )
            # Emit Prometheus metrics
            try:
                exporter = get_metrics_exporter()
                exporter.emit_intervention(
                    session_id=metrics.session_id,
                    intervention_type=intervention.type.value,
                    priority=intervention.priority.name
                )
            except Exception as e:
                logger.warning(f"Failed to emit intervention metrics: {e}")
        
        return intervention
    
    def _get_thresholds_for_domain(self, domain: str) -> Dict[str, float]:
        """Get thresholds for a specific domain."""
        base_thresholds = {
            "drift_warning": self.thresholds.drift_warning,
            "rupture_alert": self.thresholds.rupture_alert,
            "drift_velocity": self.thresholds.drift_velocity,
            "recoverability": self.thresholds.recoverability
        }
        
        # Apply domain overrides
        domain_overrides = self.DOMAIN_THRESHOLDS.get(domain, {})
        return {**base_thresholds, **domain_overrides}
    
    def _create_intervention(
        self,
        priority: InterventionPriority,
        reason: str,
        metrics: CoherenceMetrics,
        all_triggers: List[tuple]
    ) -> Optional[Intervention]:
        """
        Create appropriate intervention based on priority and mode.
        
        Args:
            priority: Highest priority trigger
            reason: Primary trigger reason
            metrics: Current metrics
            all_triggers: All triggered conditions
            
        Returns:
            Intervention or None
        """
        # Mode: silent - never intervene visibly
        if self.mode == "silent":
            return Intervention(
                type=InterventionType.SILENT,
                priority=priority,
                reason=reason,
                metrics_snapshot=metrics.to_dict(),
                action_required=False
            )
        
        # Mode: strict - intervene on any trigger
        if self.mode == "strict":
            if priority == InterventionPriority.CRITICAL:
                return Intervention(
                    type=InterventionType.HALT,
                    priority=priority,
                    reason=reason,
                    metrics_snapshot=metrics.to_dict(),
                    message="I've detected a significant coherence issue. Please clarify your question.",
                    action_required=True
                )
            elif priority == InterventionPriority.HIGH:
                return Intervention(
                    type=InterventionType.REGENERATE,
                    priority=priority,
                    reason=reason,
                    metrics_snapshot=metrics.to_dict(),
                    action_required=True
                )
            else:
                return Intervention(
                    type=InterventionType.FLAG,
                    priority=priority,
                    reason=reason,
                    metrics_snapshot=metrics.to_dict(),
                    message="I may be drifting from the topic. Let me know if I should refocus.",
                    action_required=False
                )
        
        # Mode: warn - flag but don't regenerate
        if self.mode == "warn":
            if priority == InterventionPriority.CRITICAL:
                return Intervention(
                    type=InterventionType.FLAG,
                    priority=priority,
                    reason=reason,
                    metrics_snapshot=metrics.to_dict(),
                    message="Warning: Significant topic drift detected.",
                    action_required=False
                )
            else:
                return Intervention(
                    type=InterventionType.SILENT,
                    priority=priority,
                    reason=reason,
                    metrics_snapshot=metrics.to_dict(),
                    action_required=False
                )
        
        # Mode: adaptive - smart intervention based on context
        return self._adaptive_intervention(priority, reason, metrics, all_triggers)
    
    def _adaptive_intervention(
        self,
        priority: InterventionPriority,
        reason: str,
        metrics: CoherenceMetrics,
        all_triggers: List[tuple]
    ) -> Optional[Intervention]:
        """
        Create adaptive intervention based on context.
        
        Args:
            priority: Highest priority trigger
            reason: Primary trigger reason
            metrics: Current metrics
            all_triggers: All triggered conditions
            
        Returns:
            Intervention or None
        """
        session_id = metrics.session_id
        
        # Track intervention count
        if session_id not in self._session_intervention_counts:
            self._session_intervention_counts[session_id] = 0
        
        intervention_count = self._session_intervention_counts[session_id]
        
        # Critical priority - always act
        if priority == InterventionPriority.CRITICAL:
            # Check if we've regenerated too many times
            if intervention_count >= self.interventions_config.max_regenerations:
                return Intervention(
                    type=InterventionType.FALLBACK,
                    priority=priority,
                    reason=f"{reason} (max regenerations reached)",
                    metrics_snapshot=metrics.to_dict(),
                    message=self.interventions_config.fallback_message,
                    action_required=True
                )
            
            self._session_intervention_counts[session_id] += 1
            return Intervention(
                type=InterventionType.REGENERATE,
                priority=priority,
                reason=reason,
                metrics_snapshot=metrics.to_dict(),
                action_required=True
            )
        
        # High priority - act if not too frequent
        if priority == InterventionPriority.HIGH:
            if intervention_count >= self.interventions_config.max_regenerations:
                return Intervention(
                    type=InterventionType.FLAG,
                    priority=priority,
                    reason=reason,
                    metrics_snapshot=metrics.to_dict(),
                    message="I'm having some difficulty maintaining coherence.",
                    action_required=False
                )
            
            self._session_intervention_counts[session_id] += 1
            return Intervention(
                type=InterventionType.REGENERATE,
                priority=priority,
                reason=reason,
                metrics_snapshot=metrics.to_dict(),
                action_required=True
            )
        
        # Medium priority - flag only
        if priority == InterventionPriority.MEDIUM:
            return Intervention(
                type=InterventionType.FLAG,
                priority=priority,
                reason=reason,
                metrics_snapshot=metrics.to_dict(),
                message=None,  # Silent flag
                action_required=False
            )
        
        # Low priority - silent
        return Intervention(
            type=InterventionType.SILENT,
            priority=priority,
            reason=reason,
            metrics_snapshot=metrics.to_dict(),
            action_required=False
        )
    
    def reset_session(self, session_id: str) -> None:
        """Reset intervention count for a session."""
        if session_id in self._session_intervention_counts:
            del self._session_intervention_counts[session_id]
