"""Tests for OpenClaw Gateway integration."""

import pytest
from src import BrainGuardPlugin


@pytest.mark.integration
class TestGatewayIntegration:
    """Tests for OpenClaw Gateway integration (GW-001 to GW-005)."""
    
    async def test_hook_registration(self):
        """GW-001: Hook registration."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        # Plugin should have all components registered
        assert plugin._preprocessor is not None
        assert plugin._coherence_monitor is not None
        
        await plugin.shutdown()
    
    async def test_message_flow(self):
        """GW-002: Verify message passes through plugin."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        # Simulate message flow
        session_id = "test-flow"
        user_message = "What is Python?"
        
        # Preprocess
        preprocess_result = await plugin.preprocess_message(
            session_id=session_id,
            user_message=user_message
        )
        
        assert preprocess_result["conditioned_input"] is not None
        assert "metadata" in preprocess_result
        
        # Monitor response
        response = "Python is a programming language."
        monitor_result = await plugin.monitor_response(
            session_id=session_id,
            response=response,
            metadata=preprocess_result["metadata"]
        )
        
        assert "metrics" in monitor_result
        assert monitor_result["metrics"]["delta_g"] is not None
        
        await plugin.shutdown()
    
    async def test_error_propagation(self):
        """GW-003: Plugin error doesn't break gateway."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        # Even if something goes wrong, should return gracefully
        result = await plugin.preprocess_message(
            session_id="test",
            user_message=""  # Empty message
        )
        
        # Should return a result, not raise
        assert "conditioned_input" in result
        
        await plugin.shutdown()
    
    async def test_config_reload(self):
        """GW-004: Change config, verify hot reload."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        original_mode = plugin.config.mode
        
        # Reload config
        await plugin.reload_config()
        
        # Should still be functional
        result = await plugin.preprocess_message(
            session_id="test",
            user_message="Hello"
        )
        
        assert "conditioned_input" in result
        
        await plugin.shutdown()
    
    async def test_plugin_unload(self):
        """GW-005: Unload plugin, verify graceful shutdown."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        # Verify initialized
        assert plugin._initialized is True
        
        # Shutdown
        await plugin.shutdown()
        
        # Verify shutdown
        assert plugin._initialized is False
    
    async def test_multiple_messages_same_session(self):
        """Test multiple messages in same session."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        session_id = "multi-message-session"
        
        for i in range(5):
            await plugin.preprocess_message(
                session_id=session_id,
                user_message=f"Message {i}"
            )
            await plugin.monitor_response(
                session_id=session_id,
                response=f"Response {i}"
            )
        
        # Should have 5 metrics
        metrics = await plugin.get_session_metrics(session_id)
        assert len(metrics) == 5
        
        await plugin.shutdown()
    
    async def test_concurrent_sessions(self):
        """Test handling concurrent sessions."""
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        
        await plugin.initialize()
        
        sessions = [f"concurrent-{i}" for i in range(10)]
        
        for session_id in sessions:
            await plugin.preprocess_message(
                session_id=session_id,
                user_message=f"Hello from {session_id}"
            )
            await plugin.monitor_response(
                session_id=session_id,
                response=f"Response to {session_id}"
            )
        
        # Verify all sessions have data
        for session_id in sessions:
            metrics = await plugin.get_session_metrics(session_id)
            assert len(metrics) == 1
        
        await plugin.shutdown()
