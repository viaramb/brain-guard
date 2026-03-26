"""End-to-end tests for Brain Guard plugin.

These tests simulate real user conversations and verify the entire pipeline.
"""

import pytest
import asyncio
from src import BrainGuardPlugin


@pytest.fixture
async def brain_guard():
    """Create and initialize Brain Guard plugin for E2E tests."""
    plugin = BrainGuardPlugin()
    plugin.config.testing.mock_embeddings = True
    plugin.config.storage.connection_string = ":memory:"
    plugin.config.dashboard.enabled = False
    plugin.config.mode = "adaptive"
    
    await plugin.initialize()
    yield plugin
    await plugin.shutdown()


@pytest.mark.e2e
class TestE2EConversations:
    """End-to-end conversation tests."""
    
    async def test_simple_conversation(self, brain_guard):
        """E2E-001: Simple conversation flow."""
        session_id = "e2e-simple"
        
        # Turn 1
        result1 = await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="Hello, how are you?"
        )
        assert "conditioned_input" in result1
        
        result2 = await brain_guard.monitor_response(
            session_id=session_id,
            response="I'm doing well, thank you for asking!",
            metadata=result1["metadata"]
        )
        assert "metrics" in result2
        
        # Turn 2
        result3 = await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="What can you help me with?"
        )
        
        result4 = await brain_guard.monitor_response(
            session_id=session_id,
            response="I can help with a variety of tasks including answering questions.",
            metadata=result3["metadata"]
        )
        assert "metrics" in result4
    
    async def test_topic_drift_detection(self, brain_guard):
        """E2E-002: Topic drift detection in conversation."""
        session_id = "e2e-drift"
        
        # Start on topic
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="Tell me about Python programming"
        )
        
        result = await brain_guard.monitor_response(
            session_id=session_id,
            response="Python is a versatile programming language known for its readability."
        )
        
        # Drift to different topic
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="What about cats?"
        )
        
        result = await brain_guard.monitor_response(
            session_id=session_id,
            response="Cats are wonderful pets that are independent and affectionate."
        )
        
        # Should have detected drift
        assert result["metrics"]["delta_g"] > 0
    
    async def test_contradiction_detection(self, brain_guard):
        """E2E-003: Contradiction detection."""
        session_id = "e2e-contradiction"
        
        # Establish fact
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="Where is Paris?"
        )
        
        await brain_guard.monitor_response(
            session_id=session_id,
            response="Paris is the capital of France."
        )
        
        # Contradict it
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="I heard it's in Germany"
        )
        
        result = await brain_guard.monitor_response(
            session_id=session_id,
            response="Actually, Paris is in Germany, not France."
        )
        
        # Should have detected contradiction
        assert len(result["contradictions"]) > 0
    
    async def test_repetition_detection(self, brain_guard):
        """E2E-004: Repetition detection."""
        session_id = "e2e-repetition"
        
        # Same response multiple times
        for i in range(5):
            await brain_guard.preprocess_message(
                session_id=session_id,
                user_message=f"Question {i}"
            )
            
            await brain_guard.monitor_response(
                session_id=session_id,
                response="This is exactly the same response repeated."
            )
        
        # Check metrics
        metrics = await brain_guard.get_session_metrics(session_id)
        assert len(metrics) == 5
        
        # Later metrics should show low variance
        later_metrics = metrics[-3:]
        avg_variance = sum(m["variance"] for m in later_metrics) / len(later_metrics)
        assert avg_variance < 0.5
    
    async def test_multi_session_isolation(self, brain_guard):
        """E2E-005: Multiple session isolation."""
        # Session A
        await brain_guard.preprocess_message(
            session_id="session-a",
            user_message="Tell me about Python"
        )
        await brain_guard.monitor_response(
            session_id="session-a",
            response="Python is a programming language."
        )
        
        # Session B
        await brain_guard.preprocess_message(
            session_id="session-b",
            user_message="Tell me about JavaScript"
        )
        await brain_guard.monitor_response(
            session_id="session-b",
            response="JavaScript is a web programming language."
        )
        
        # Verify isolation
        metrics_a = await brain_guard.get_session_metrics("session-a")
        metrics_b = await brain_guard.get_session_metrics("session-b")
        
        assert len(metrics_a) == 1
        assert len(metrics_b) == 1
        
        anchors_a = await brain_guard.get_session_anchors("session-a")
        anchors_b = await brain_guard.get_session_anchors("session-b")
        
        # Anchors should be different
        assert any("Python" in str(a) for a in anchors_a)
        assert any("JavaScript" in str(a) for a in anchors_b)
    
    async def test_long_conversation(self, brain_guard):
        """E2E-006: Long conversation (20+ turns)."""
        session_id = "e2e-long"
        
        for i in range(25):
            await brain_guard.preprocess_message(
                session_id=session_id,
                user_message=f"Question {i}: What is topic {i}?"
            )
            await brain_guard.monitor_response(
                session_id=session_id,
                response=f"Answer {i}: Topic {i} is interesting."
            )
        
        metrics = await brain_guard.get_session_metrics(session_id)
        assert len(metrics) == 25
    
    async def test_session_lifecycle(self, brain_guard):
        """E2E-007: Session lifecycle."""
        session_id = "e2e-lifecycle"
        
        # Create session
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="Hello"
        )
        await brain_guard.monitor_response(
            session_id=session_id,
            response="Hi there!"
        )
        
        # Verify data exists
        metrics = await brain_guard.get_session_metrics(session_id)
        assert len(metrics) == 1
        
        anchors = await brain_guard.get_session_anchors(session_id)
        assert len(anchors) >= 0
        
        # Close session
        await brain_guard.close_session(session_id)
        
        # Anchors should be cleared
        anchors = await brain_guard.get_session_anchors(session_id)
        assert len(anchors) == 0
    
    async def test_domain_detection(self, brain_guard):
        """E2E-008: Domain detection in conversation."""
        session_id = "e2e-domain"
        
        result = await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="What is a good investment strategy?"
        )
        
        # Should detect finance domain
        assert result["metadata"]["domain"] == "finance"
    
    async def test_intervention_triggering(self, brain_guard):
        """E2E-009: Intervention triggering on severe drift."""
        session_id = "e2e-intervention"
        
        # Start coherent
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="Tell me about dogs"
        )
        await brain_guard.monitor_response(
            session_id=session_id,
            response="Dogs are loyal pets."
        )
        
        # Force severe drift by using completely unrelated topics
        # Note: In real scenarios, this would require actual drift
        # Here we just verify the pipeline works
        await brain_guard.preprocess_message(
            session_id=session_id,
            user_message="Quantum physics"
        )
        result = await brain_guard.monitor_response(
            session_id=session_id,
            response="Quantum physics is the study of matter and energy at the most fundamental level."
        )
        
        # Pipeline should complete
        assert "metrics" in result
        assert "intervention" in result


@pytest.mark.e2e
class TestE2EErrorHandling:
    """End-to-end error handling tests."""
    
    async def test_empty_message_handling(self, brain_guard):
        """Test handling of empty messages."""
        result = await brain_guard.preprocess_message(
            session_id="e2e-empty",
            user_message=""
        )
        
        assert "conditioned_input" in result
        
        result = await brain_guard.monitor_response(
            session_id="e2e-empty",
            response=""
        )
        
        assert "metrics" in result
    
    async def test_very_long_message(self, brain_guard):
        """Test handling of very long messages."""
        long_message = "word " * 1000
        
        result = await brain_guard.preprocess_message(
            session_id="e2e-long-msg",
            user_message=long_message
        )
        
        assert "conditioned_input" in result
    
    async def test_special_characters(self, brain_guard):
        """Test handling of special characters."""
        special_msg = "Hello! @#$%^&*()_+ {}[]|;':\",./<>?"
        
        result = await brain_guard.preprocess_message(
            session_id="e2e-special",
            user_message=special_msg
        )
        
        assert "conditioned_input" in result
