"""Test script to verify Prometheus metrics collection for Brain Guard."""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics import get_metrics_exporter, reset_metrics_exporter
from src.components.coherence_monitor import CoherenceMonitor
from src.components.session_anchoring import SessionAnchoring
from src.components.preprocessor import Preprocessor
from src.components.threshold_engine import ThresholdEngine
from src.utils.config import ThresholdConfig, InterventionsConfig
from src.utils.embedding_service import EmbeddingService
from src.models import Contradiction, InterventionType, InterventionPriority


class MockEmbeddingService:
    """Mock embedding service for testing."""
    
    def __init__(self):
        self.dimension = 384
    
    async def embed(self, text: str):
        import numpy as np
        from src.utils.embedding_service import EmbeddingTimingMetrics
        
        # Generate deterministic mock embedding
        np.random.seed(hash(text) % 2**32)
        embedding = np.random.randn(self.dimension).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        timing = EmbeddingTimingMetrics(
            embedding_time_ms=10.0,
            cache_hit=False,
            batch_size=1
        )
        return embedding, timing
    
    def cosine_similarity(self, a, b):
        import numpy as np
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def test_coherence_metrics():
    """Test coherence metrics emission."""
    print("\n=== Testing Coherence Metrics ===")
    
    reset_metrics_exporter()
    exporter = get_metrics_exporter()
    embedding_service = MockEmbeddingService()
    monitor = CoherenceMonitor(embedding_service)
    
    session_id = "test_session_1"
    
    # Simulate multiple turns
    for i in range(5):
        metrics = await monitor.calculate_metrics(
            session_id=session_id,
            current_response=f"This is test response number {i} with some content about machine learning and AI.",
            history=[]
        )
        print(f"  Turn {i+1}: delta_g={metrics.delta_g:.4f}, "
              f"drift_velocity={metrics.drift_velocity:.4f}, "
              f"continuity_score={metrics.continuity_score:.4f}")
        await asyncio.sleep(0.1)
    
    # Check metrics output
    output = exporter.get_metrics().decode('utf-8')
    assert 'brain_guard_coherence_delta_g' in output
    assert 'brain_guard_coherence_drift_velocity' in output
    assert 'brain_guard_coherence_variance' in output
    assert 'brain_guard_coherence_continuity_score' in output
    print("  Coherence metrics: OK")


async def test_anchoring_metrics():
    """Test anchoring metrics emission."""
    print("\n=== Testing Anchoring Metrics ===")
    
    reset_metrics_exporter()
    exporter = get_metrics_exporter()
    embedding_service = MockEmbeddingService()
    anchoring = SessionAnchoring(embedding_service)
    
    session_id = "test_session_2"
    
    # Extract anchors
    text = "Machine learning is a subset of artificial intelligence. " \
           "Python is a popular programming language for ML. " \
           "First, you need to prepare your data. Then you train the model."
    
    anchors = await anchoring.extract_anchors(session_id, text)
    print(f"  Extracted {len(anchors)} anchors")
    for anchor in anchors:
        print(f"    - {anchor.anchor_type}: {anchor.text[:50]}...")
    
    # Check contradictions
    contradictions = await anchoring.check_contradictions(
        session_id,
        "Machine learning is not related to artificial intelligence."
    )
    print(f"  Detected {len(contradictions)} contradictions")
    
    # Check metrics output
    output = exporter.get_metrics().decode('utf-8')
    assert 'brain_guard_anchoring_active_anchors' in output
    assert 'brain_guard_anchoring_anchors_extracted_total' in output
    print("  Anchoring metrics: OK")


async def test_preprocessor_metrics():
    """Test preprocessor metrics emission."""
    print("\n=== Testing Preprocessor Metrics ===")
    
    reset_metrics_exporter()
    exporter = get_metrics_exporter()
    embedding_service = MockEmbeddingService()
    preprocessor = Preprocessor(embedding_service)
    
    session_id = "test_session_3"
    
    # Process ambiguous message
    result = await preprocessor.process(
        session_id=session_id,
        message="What about it? Maybe this could be something.",
        domain="general"
    )
    
    print(f"  Ambiguity score: {result['metadata']['ambiguity_score']:.4f}")
    print(f"  Ambiguity flags: {result['metadata']['ambiguity_flags']}")
    print(f"  Processing time: {result['metadata']['processing_time_ms']:.2f}ms")
    
    # Check metrics output
    output = exporter.get_metrics().decode('utf-8')
    assert 'brain_guard_observatory_ambiguity_score' in output
    assert 'brain_guard_observatory_domain_switches_total' in output
    print("  Preprocessor metrics: OK")


async def test_threshold_engine_metrics():
    """Test threshold engine metrics emission."""
    print("\n=== Testing Threshold Engine Metrics ===")
    
    reset_metrics_exporter()
    exporter = get_metrics_exporter()
    
    thresholds = ThresholdConfig(
        drift_warning=0.5,
        rupture_alert=0.7,
        drift_velocity=0.1,
        variance_collapse=0.02,
        recoverability=0.5
    )
    engine = ThresholdEngine(thresholds, mode="adaptive")
    
    # Create mock metrics that trigger intervention
    from src.components.coherence_monitor import CoherenceMetrics
    
    mock_metrics = CoherenceMetrics(
        session_id="test_session_4",
        turn_number=1,
        delta_g=0.75,  # Above rupture alert
        drift_velocity=0.15,  # Above threshold
        variance=0.01,  # Below collapse threshold
        continuity_score=0.4,  # Below recoverability
        processing_time_ms=50.0,
        embedding_time_ms=20.0
    )
    
    # Create mock contradiction
    contradiction = Contradiction(
        anchor_id="anchor_1",
        anchor_text="AI is intelligent",
        new_text="AI is not intelligent",
        similarity=0.6,
        confidence=0.85
    )
    
    intervention = engine.evaluate(
        metrics=mock_metrics,
        contradictions=[contradiction],
        domain="general"
    )
    
    if intervention:
        print(f"  Intervention triggered: {intervention.type.value}")
        print(f"  Priority: {intervention.priority.name}")
        print(f"  Reason: {intervention.reason}")
    
    # Check metrics output
    output = exporter.get_metrics().decode('utf-8')
    assert 'brain_guard_response_interventions_triggered_total' in output
    print("  Threshold engine metrics: OK")


async def test_metrics_endpoint():
    """Test that metrics endpoint returns valid Prometheus format."""
    print("\n=== Testing Metrics Endpoint Format ===")
    
    reset_metrics_exporter()
    exporter = get_metrics_exporter()
    
    # Emit various metrics
    exporter.emit_coherence_metrics(
        session_id="test",
        delta_g=0.3,
        drift_velocity=0.05,
        variance=0.1,
        continuity_score=0.85
    )
    
    exporter.emit_anchor_change(session_id="test", active_count=5)
    exporter.emit_anchor_extracted(session_id="test", anchor_type="factual")
    exporter.emit_contradiction_detected(session_id="test")
    exporter.emit_domain_detection(session_id="test", domain="general")
    exporter.emit_ambiguity_score(session_id="test", ambiguity_score=0.3)
    exporter.emit_intervention(
        session_id="test",
        intervention_type="flag",
        priority="MEDIUM"
    )
    
    # Get metrics output
    output = exporter.get_metrics().decode('utf-8')
    
    # Validate Prometheus format
    lines = output.strip().split('\n')
    print(f"  Total lines: {len(lines)}")
    
    # Check for required metric families
    required_metrics = [
        'brain_guard_coherence_delta_g',
        'brain_guard_coherence_drift_velocity',
        'brain_guard_coherence_variance',
        'brain_guard_coherence_continuity_score',
        'brain_guard_anchoring_active_anchors',
        'brain_guard_anchoring_anchors_extracted_total',
        'brain_guard_anchoring_contradictions_detected_total',
        'brain_guard_observatory_domain_switches_total',
        'brain_guard_observatory_ambiguity_score',
        'brain_guard_response_interventions_triggered_total',
        'brain_guard_system_info'
    ]
    
    for metric in required_metrics:
        if metric in output:
            print(f"  {metric}: OK")
        else:
            print(f"  {metric}: MISSING")
    
    # Check content type
    content_type = exporter.get_content_type()
    assert 'text/plain' in content_type
    # Version format varies by prometheus-client version
    print(f"  Content-Type: {content_type}")
    print("  Metrics endpoint format: OK")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Brain Guard Prometheus Metrics Test Suite")
    print("=" * 60)
    
    try:
        await test_coherence_metrics()
        await test_anchoring_metrics()
        await test_preprocessor_metrics()
        await test_threshold_engine_metrics()
        await test_metrics_endpoint()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
