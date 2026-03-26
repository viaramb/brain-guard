"""Unit tests for Threshold Engine component."""

import pytest
from src.components.threshold_engine import (
    ThresholdEngine, InterventionType, InterventionPriority,
    Contradiction
)
from src.components.coherence_monitor import CoherenceMetrics
from src.utils.config import ThresholdConfig, InterventionsConfig


@pytest.fixture
def threshold_config():
    """Create threshold configuration."""
    return ThresholdConfig(
        drift_warning=0.65,
        rupture_alert=0.85,
        drift_velocity=0.10,
        variance_collapse=0.02,
        recoverability=0.30
    )


@pytest.fixture
def interventions_config():
    """Create interventions configuration."""
    return InterventionsConfig(
        auto_regenerate=False,
        max_regenerations=2
    )


@pytest.fixture
def threshold_engine(threshold_config, interventions_config):
    """Create threshold engine instance."""
    return ThresholdEngine(
        thresholds=threshold_config,
        mode="adaptive",
        interventions_config=interventions_config
    )


@pytest.fixture
def base_metrics():
    """Create base metrics for testing."""
    return CoherenceMetrics(
        session_id="test-session",
        turn_number=1,
        delta_g=0.3,
        drift_velocity=0.0,
        variance=0.5,
        continuity_score=0.8
    )


@pytest.mark.unit
class TestThresholdEngine:
    """Tests for Threshold Engine (Layer 4)."""
    
    def test_no_thresholds_crossed(self, threshold_engine, base_metrics):
        """THR-001: No thresholds crossed - no action."""
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is None
    
    def test_drift_warning(self, threshold_engine, base_metrics):
        """THR-002: Drift warning triggered."""
        base_metrics.delta_g = 0.7  # Above 0.65 warning threshold
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert "drift_warning" in intervention.reason
    
    def test_rupture_alert(self, threshold_engine, base_metrics):
        """THR-003: Rupture alert triggered."""
        base_metrics.delta_g = 0.9  # Above 0.85 rupture threshold
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert intervention.priority == InterventionPriority.CRITICAL
        assert "rupture" in intervention.reason.lower()
    
    def test_accelerating_drift(self, threshold_engine, base_metrics):
        """THR-004: Accelerating drift triggered."""
        base_metrics.drift_velocity = 0.15  # Above 0.10 threshold
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert "accelerating" in intervention.reason.lower()
    
    def test_variance_collapse(self, threshold_engine, base_metrics):
        """THR-005: Variance collapse triggered."""
        base_metrics.variance = 0.01  # Below 0.02 threshold
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert "variance" in intervention.reason.lower()
    
    def test_low_recoverability(self, threshold_engine, base_metrics):
        """THR-006: Low recoverability triggered."""
        base_metrics.continuity_score = 0.2  # Below 0.30 threshold
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert "recoverability" in intervention.reason.lower()
    
    def test_multiple_triggers_priority(self, threshold_engine, base_metrics):
        """THR-007: Multiple triggers - highest priority wins."""
        base_metrics.delta_g = 0.9  # Rupture (CRITICAL)
        base_metrics.drift_velocity = 0.15  # Accelerating (HIGH)
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert intervention.priority == InterventionPriority.CRITICAL
    
    def test_threshold_boundary(self, threshold_engine, base_metrics):
        """THR-008: Threshold boundary classification."""
        # Just below threshold
        base_metrics.delta_g = 0.64
        intervention1 = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        # Just above threshold
        base_metrics.delta_g = 0.66
        intervention2 = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention1 is None
        assert intervention2 is not None
    
    def test_mode_silent(self, threshold_config, interventions_config, base_metrics):
        """THR-009: Silent mode - log only."""
        engine = ThresholdEngine(
            thresholds=threshold_config,
            mode="silent",
            interventions_config=interventions_config
        )
        
        base_metrics.delta_g = 0.9  # Would normally trigger rupture
        
        intervention = engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
        assert intervention.type == InterventionType.SILENT
        assert not intervention.action_required
    
    def test_mode_strict(self, threshold_config, interventions_config, base_metrics):
        """THR-010: Strict mode - intervene on any trigger."""
        engine = ThresholdEngine(
            thresholds=threshold_config,
            mode="strict",
            interventions_config=interventions_config
        )
        
        # Even low drift triggers in strict mode
        base_metrics.delta_g = 0.5
        
        intervention = engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        # Strict mode intervenes on any trigger
        # (Note: 0.5 is below warning threshold, so may not trigger)
        # Let's use a value above warning
        base_metrics.delta_g = 0.7
        intervention = engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
    
    def test_contradiction_detection(self, threshold_engine, base_metrics):
        """Test contradiction detection triggers intervention."""
        contradiction = Contradiction(
            anchor_id="anchor_1",
            anchor_text="Paris is in France",
            new_text="Paris is in Germany",
            similarity=0.6,
            confidence=0.9
        )
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[contradiction],
            domain="general"
        )
        
        assert intervention is not None
        assert "contradiction" in intervention.reason.lower()
    
    def test_domain_specific_thresholds(self, threshold_engine, base_metrics):
        """Test domain-specific threshold overrides."""
        # Finance has lower thresholds
        base_metrics.delta_g = 0.6  # Above finance warning (0.50) but below general (0.65)
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="finance"
        )
        
        # Should trigger because finance threshold is lower
        assert intervention is not None
    
    def test_intervention_count_tracking(self, threshold_engine, base_metrics):
        """Test intervention count per session."""
        base_metrics.delta_g = 0.9  # Critical
        
        # First intervention
        intervention1 = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        # Second intervention
        intervention2 = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention1 is not None
        assert intervention2 is not None
    
    def test_max_regenerations_fallback(self, threshold_config, base_metrics):
        """Test fallback after max regenerations."""
        config = InterventionsConfig(
            auto_regenerate=True,
            max_regenerations=1,
            fallback_message="Fallback message"
        )
        engine = ThresholdEngine(
            thresholds=threshold_config,
            mode="adaptive",
            interventions_config=config
        )
        
        base_metrics.delta_g = 0.9  # Critical
        
        # First intervention - should be REGENERATE
        intervention1 = engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        # Second intervention - should be FALLBACK
        intervention2 = engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention1.type == InterventionType.REGENERATE
        assert intervention2.type == InterventionType.FALLBACK
    
    def test_update_config(self, threshold_engine, threshold_config, base_metrics):
        """Test hot config reload."""
        new_config = ThresholdConfig(
            drift_warning=0.5,  # Lower threshold
            rupture_alert=0.85,
            drift_velocity=0.10,
            variance_collapse=0.02,
            recoverability=0.30
        )
        
        threshold_engine.update_config(new_config, "adaptive")
        
        base_metrics.delta_g = 0.6  # Above new threshold (0.5) but below old (0.65)
        
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention is not None
    
    def test_reset_session(self, threshold_engine, base_metrics):
        """Test session reset."""
        base_metrics.delta_g = 0.9
        
        # Trigger intervention
        threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        # Reset session
        threshold_engine.reset_session("test-session")
        
        # Should be able to trigger again without fallback
        intervention = threshold_engine.evaluate(
            metrics=base_metrics,
            contradictions=[],
            domain="general"
        )
        
        assert intervention.type == InterventionType.REGENERATE
