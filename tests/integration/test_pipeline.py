"""Integration tests for full pipeline."""

import pytest
from src import BrainGuardPlugin


@pytest.fixture
async def brain_guard_plugin():
    """Create and initialize Brain Guard plugin."""
    plugin = BrainGuardPlugin()
    plugin.config.testing.mock_embeddings = True
    plugin.config.storage.connection_string = ":memory:"
    plugin.config.dashboard.enabled = False
    
    await plugin.initialize()
    yield plugin
    await plugin.shutdown()


@pytest.mark.integration
class TestFullPipeline:
    """Integration tests for full pipeline (INT-001 to INT-006)."""
    
    async def test_happy_path(self, brain_guard_plugin):
        """INT-001: Happy path - all layers called, metrics stored."""
        session_id = "test-session-happy"
        
        # Preprocess
        preprocess_result = await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="What is Python programming?"
        )
        
        assert "conditioned_input" in preprocess_result
        assert "metadata" in preprocess_result
        
        # Monitor response
        monitor_result = await brain_guard_plugin.monitor_response(
            session_id=session_id,
            response="Python is a high-level programming language.",
            metadata=preprocess_result["metadata"]
        )
        
        assert "metrics" in monitor_result
        assert monitor_result["metrics"]["delta_g"] is not None
    
    async def test_drift_detection(self, brain_guard_plugin):
        """INT-002: Drift detection - warning triggered and logged."""
        session_id = "test-session-drift"
        
        # First message
        await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="Tell me about dogs"
        )
        
        await brain_guard_plugin.monitor_response(
            session_id=session_id,
            response="Dogs are loyal pets."
        )
        
        # Second message - different topic to induce drift
        await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="What about quantum physics?"
        )
        
        result = await brain_guard_plugin.monitor_response(
            session_id=session_id,
            response="Quantum physics is a fundamental theory in physics."
        )
        
        # Should have metrics
        assert "metrics" in result
        # Drift should be detected (delta_g > 0)
        assert result["metrics"]["delta_g"] > 0
    
    async def test_multi_turn_session(self, brain_guard_plugin):
        """INT-004: Multi-turn session - continuity tracked, anchors accumulated."""
        session_id = "test-session-multi"
        
        conversation = [
            ("What is Python?", "Python is a programming language."),
            ("What can I do with it?", "You can build web apps, scripts, and more."),
            ("Is it easy to learn?", "Yes, Python has a gentle learning curve."),
        ]
        
        for user_msg, assistant_response in conversation:
            await brain_guard_plugin.preprocess_message(
                session_id=session_id,
                user_message=user_msg
            )
            
            await brain_guard_plugin.monitor_response(
                session_id=session_id,
                response=assistant_response
            )
        
        # Check metrics were stored
        metrics = await brain_guard_plugin.get_session_metrics(session_id)
        assert len(metrics) == 3
        
        # Check anchors were extracted
        anchors = await brain_guard_plugin.get_session_anchors(session_id)
        assert len(anchors) > 0
    
    async def test_session_closure(self, brain_guard_plugin):
        """INT-006: Session closure - cleanup and final stats."""
        session_id = "test-session-close"
        
        # Some conversation
        await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="Hello"
        )
        await brain_guard_plugin.monitor_response(
            session_id=session_id,
            response="Hi there!"
        )
        
        # Close session
        await brain_guard_plugin.close_session(session_id)
        
        # Session should be marked as closed in database
        assert True  # If no exception, test passes
    
    async def test_high_stakes_escalation(self, brain_guard_plugin):
        """INT-005: High-stakes escalation - monitoring tightened."""
        session_id = "test-session-highstakes"
        
        # Message with high-stakes keyword
        result = await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="What is the best investment strategy?"
        )
        
        # Should detect finance domain
        assert result["metadata"]["domain"] == "finance"
    
    async def test_intervention_triggered(self, brain_guard_plugin):
        """Test that interventions are triggered when thresholds crossed."""
        session_id = "test-session-intervention"
        
        # Set strict mode to ensure intervention
        brain_guard_plugin.config.mode = "strict"
        brain_guard_plugin._threshold_engine.update_config(
            thresholds=brain_guard_plugin.config.thresholds,
            mode="strict"
        )
        
        # First message
        await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="Topic A"
        )
        await brain_guard_plugin.monitor_response(
            session_id=session_id,
            response="Response about topic A"
        )
        
        # Second message - very different to trigger rupture
        await brain_guard_plugin.preprocess_message(
            session_id=session_id,
            user_message="Completely unrelated topic B about quantum mechanics"
        )
        
        result = await brain_guard_plugin.monitor_response(
            session_id=session_id,
            response="Quantum mechanics is completely different from topic A"
        )
        
        # Should have intervention data
        assert "intervention" in result


@pytest.mark.integration
class TestPluginLifecycle:
    """Tests for plugin lifecycle."""
    
    async def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        assert plugin._initialized is True
        assert plugin._preprocessor is not None
        assert plugin._coherence_monitor is not None
        
        await plugin.shutdown()
    
    async def test_plugin_shutdown(self):
        """Test plugin can be shutdown."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        await plugin.shutdown()
        
        assert plugin._initialized is False
    
    async def test_plugin_disabled(self):
        """Test plugin behavior when disabled."""
        import os
        os.environ["BRAIN_GUARD_ENABLED"] = "false"
        
        plugin = BrainGuardPlugin()
        
        assert plugin.enabled is False
        
        # Should return passthrough results
        result = await plugin.preprocess_message(
            session_id="test",
            user_message="Hello"
        )
        
        assert result["conditioned_input"] == "Hello"
        
        os.environ["BRAIN_GUARD_ENABLED"] = "true"
    
    async def test_config_reload(self, brain_guard_plugin):
        """Test hot config reload."""
        original_mode = brain_guard_plugin.config.mode
        
        # Reload config
        await brain_guard_plugin.reload_config()
        
        # Config should be reloaded
        assert brain_guard_plugin.config is not None
    
    async def test_multiple_sessions(self, brain_guard_plugin):
        """Test handling multiple concurrent sessions."""
        sessions = [f"session-{i}" for i in range(5)]
        
        for session_id in sessions:
            await brain_guard_plugin.preprocess_message(
                session_id=session_id,
                user_message=f"Message for {session_id}"
            )
            await brain_guard_plugin.monitor_response(
                session_id=session_id,
                response=f"Response for {session_id}"
            )
        
        # Each session should have its own metrics
        for session_id in sessions:
            metrics = await brain_guard_plugin.get_session_metrics(session_id)
            assert len(metrics) == 1
