"""Prometheus metrics exporter for Brain Guard SCFL-Quad monitoring."""

import time
from typing import Dict, Any, Optional
from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST


class PrometheusExporter:
    """
    Prometheus metrics exporter for all SCFL-Quad components.
    
    Coherence Layer (CFM):
    - delta_g: Coherence deformation gauge
    - drift_velocity: Drift velocity gauge
    - variance: Variance gauge
    - continuity_score: Continuity score gauge
    
    Anchoring Layer (SAS):
    - active_anchors: Number of active anchors gauge
    - contradictions_detected: Counter for contradictions
    - anchors_extracted: Counter for extracted anchors
    
    Observatory Layer (CDO):
    - domain_switches: Counter for domain switches
    - risk_score: Risk score gauge
    - ambiguity_score: Ambiguity score gauge
    
    Response Layer (RCE):
    - interventions_triggered: Counter for interventions
    - latency_ms: Histogram for response latency
    - processing_time_ms: Histogram for processing time
    """
    
    def __init__(self):
        # Coherence metrics (CFM)
        self.coherence_delta_g = Gauge(
            'brain_guard_coherence_delta_g',
            'Coherence deformation (0 = identical, 1 = orthogonal)',
            ['session_id']
        )
        self.coherence_drift_velocity = Gauge(
            'brain_guard_coherence_drift_velocity',
            'Drift velocity (positive = accelerating drift)',
            ['session_id']
        )
        self.coherence_variance = Gauge(
            'brain_guard_coherence_variance',
            'Response variance across embedding window',
            ['session_id']
        )
        self.coherence_continuity_score = Gauge(
            'brain_guard_coherence_continuity_score',
            'Overall continuity score (0-1, higher is better)',
            ['session_id']
        )
        self.coherence_processing_time = Histogram(
            'brain_guard_coherence_processing_seconds',
            'Time spent calculating coherence metrics',
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )
        
        # Anchoring metrics (SAS)
        self.anchoring_active_anchors = Gauge(
            'brain_guard_anchoring_active_anchors',
            'Number of active anchors for session',
            ['session_id']
        )
        self.anchoring_contradictions = Counter(
            'brain_guard_anchoring_contradictions_detected_total',
            'Total contradictions detected',
            ['session_id']
        )
        self.anchoring_anchors_extracted = Counter(
            'brain_guard_anchoring_anchors_extracted_total',
            'Total anchors extracted',
            ['session_id', 'anchor_type']
        )
        
        # Observatory metrics (CDO)
        self.observatory_domain_switches = Counter(
            'brain_guard_observatory_domain_switches_total',
            'Total domain switches',
            ['session_id', 'from_domain', 'to_domain']
        )
        self.observatory_risk_score = Gauge(
            'brain_guard_observatory_risk_score',
            'Current risk score for session',
            ['session_id', 'domain']
        )
        self.observatory_ambiguity_score = Gauge(
            'brain_guard_observatory_ambiguity_score',
            'Input ambiguity score (0-1)',
            ['session_id']
        )
        
        # Response metrics (RCE)
        self.response_interventions = Counter(
            'brain_guard_response_interventions_triggered_total',
            'Total interventions triggered',
            ['session_id', 'intervention_type', 'priority']
        )
        self.response_latency = Histogram(
            'brain_guard_response_latency_seconds',
            'Response latency in seconds',
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        self.response_processing_time = Histogram(
            'brain_guard_response_processing_seconds',
            'Response processing time in seconds',
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )
        
        # System info
        self.system_info = Info(
            'brain_guard_system',
            'Brain Guard system information'
        )
        self.system_info.info({'version': '1.0.0', 'name': 'Brain Guard'})
        
        # Track session states
        self._session_domains: Dict[str, str] = {}
        self._session_anchor_counts: Dict[str, int] = {}
    
    # Coherence metrics methods
    def emit_coherence_metrics(
        self,
        session_id: str,
        delta_g: float,
        drift_velocity: float,
        variance: float,
        continuity_score: float,
        processing_time_ms: float = 0.0
    ) -> None:
        """Emit coherence metrics after each calculation."""
        self.coherence_delta_g.labels(session_id=session_id).set(delta_g)
        self.coherence_drift_velocity.labels(session_id=session_id).set(drift_velocity)
        self.coherence_variance.labels(session_id=session_id).set(variance)
        self.coherence_continuity_score.labels(session_id=session_id).set(continuity_score)
        if processing_time_ms > 0:
            self.coherence_processing_time.observe(processing_time_ms / 1000.0)
    
    # Anchoring metrics methods
    def emit_anchor_extracted(
        self,
        session_id: str,
        anchor_type: str,
        count: int = 1
    ) -> None:
        """Emit metric when anchors are extracted."""
        self.anchoring_anchors_extracted.labels(
            session_id=session_id,
            anchor_type=anchor_type
        ).inc(count)
    
    def emit_anchor_change(
        self,
        session_id: str,
        active_count: int
    ) -> None:
        """Emit metric on anchor changes."""
        self.anchoring_active_anchors.labels(session_id=session_id).set(active_count)
        self._session_anchor_counts[session_id] = active_count
    
    def emit_contradiction_detected(
        self,
        session_id: str,
        count: int = 1
    ) -> None:
        """Emit metric when contradictions are detected."""
        self.anchoring_contradictions.labels(session_id=session_id).inc(count)
    
    # Observatory metrics methods
    def emit_domain_detection(
        self,
        session_id: str,
        domain: str
    ) -> None:
        """Emit metric on domain detection."""
        previous_domain = self._session_domains.get(session_id)
        if previous_domain and previous_domain != domain:
            self.observatory_domain_switches.labels(
                session_id=session_id,
                from_domain=previous_domain,
                to_domain=domain
            ).inc()
        self._session_domains[session_id] = domain
    
    def emit_ambiguity_score(
        self,
        session_id: str,
        ambiguity_score: float
    ) -> None:
        """Emit ambiguity score metric."""
        self.observatory_ambiguity_score.labels(session_id=session_id).set(ambiguity_score)
    
    def emit_risk_score(
        self,
        session_id: str,
        domain: str,
        risk_score: float
    ) -> None:
        """Emit risk score metric."""
        self.observatory_risk_score.labels(
            session_id=session_id,
            domain=domain
        ).set(risk_score)
    
    # Response metrics methods
    def emit_intervention(
        self,
        session_id: str,
        intervention_type: str,
        priority: str
    ) -> None:
        """Emit metric when intervention is triggered."""
        self.response_interventions.labels(
            session_id=session_id,
            intervention_type=intervention_type,
            priority=priority
        ).inc()
    
    def emit_response_latency(self, latency_ms: float) -> None:
        """Emit response latency metric."""
        self.response_latency.observe(latency_ms / 1000.0)
    
    def emit_processing_time(self, processing_time_ms: float) -> None:
        """Emit processing time metric."""
        self.response_processing_time.observe(processing_time_ms / 1000.0)
    
    def get_metrics(self) -> bytes:
        """Get Prometheus-formatted metrics."""
        return generate_latest()
    
    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        return CONTENT_TYPE_LATEST
    
    def clear_session(self, session_id: str) -> None:
        """Clear session-specific metrics."""
        if session_id in self._session_domains:
            del self._session_domains[session_id]
        if session_id in self._session_anchor_counts:
            del self._session_anchor_counts[session_id]


# Global exporter instance
_metrics_exporter: Optional[PrometheusExporter] = None


def get_metrics_exporter() -> PrometheusExporter:
    """Get or create the global metrics exporter instance."""
    global _metrics_exporter
    if _metrics_exporter is None:
        _metrics_exporter = PrometheusExporter()
    return _metrics_exporter


def reset_metrics_exporter() -> None:
    """Reset the global metrics exporter (useful for testing)."""
    global _metrics_exporter
    from prometheus_client import REGISTRY
    
    # Unregister all Brain Guard metrics from the registry
    if _metrics_exporter is not None:
        collectors_to_remove = []
        for collector in REGISTRY._collector_to_names.keys():
            # Check if this collector belongs to brain_guard
            names = REGISTRY._collector_to_names.get(collector, set())
            if any('brain_guard' in name for name in names):
                collectors_to_remove.append(collector)
        
        for collector in collectors_to_remove:
            try:
                REGISTRY.unregister(collector)
            except Exception:
                pass
    
    _metrics_exporter = None
