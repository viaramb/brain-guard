"""Tests for main plugin entry point."""

import pytest
import os
from src import BrainGuardPlugin, get_plugin, initialize_plugin


@pytest.mark.unit
class TestBrainGuardPlugin:
    """Tests for BrainGuardPlugin main class."""

    def test_plugin_creation(self):
        """Test plugin can be created."""
        plugin = BrainGuardPlugin()
        assert plugin is not None
        assert hasattr(plugin, 'config')
    
    def test_check_enabled_default(self, monkeypatch):
        """Test enabled check with default."""
        # Ensure env var is not set
        monkeypatch.delenv("BRAIN_GUARD_ENABLED", raising=False)
        
        plugin = BrainGuardPlugin()
        # Default should be False when env var not set
        assert plugin._check_enabled() is False
    
    def test_check_enabled_true(self, monkeypatch):
        """Test enabled check with true value."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        assert plugin._check_enabled() is True
    
    def test_check_enabled_false(self, monkeypatch):
        """Test enabled check with false value."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "false")
        plugin = BrainGuardPlugin()
        assert plugin._check_enabled() is False
    
    async def test_initialize_mock_mode(self, monkeypatch):
        """Test plugin initialization with mock embeddings."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        await plugin.initialize()
        
        assert plugin._initialized is True
        assert plugin._preprocessor is not None
        assert plugin._coherence_monitor is not None
        assert plugin._threshold_engine is not None
        assert plugin._session_anchoring is not None
        assert plugin._domain_detector is not None
        assert plugin._db_manager is not None
        
        await plugin.shutdown()
    
    async def test_disabled_plugin_behavior(self, monkeypatch):
        """Test plugin behavior when disabled."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "false")
        
        plugin = BrainGuardPlugin()
        await plugin.initialize()
        
        # Should return passthrough results
        result = await plugin.preprocess_message(
            session_id="test",
            user_message="Hello"
        )
        
        assert result["conditioned_input"] == "Hello"
        assert result["metadata"] == {}
        
        result = await plugin.monitor_response(
            session_id="test",
            response="Hi"
        )
        
        assert result["metrics"] == {}
        assert result["intervention"] is None
    
    async def test_preprocess_message(self, monkeypatch):
        """Test preprocess message."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        await plugin.initialize()
        
        result = await plugin.preprocess_message(
            session_id="test-session",
            user_message="What is Python?",
            context={"user": "test"}
        )
        
        assert "conditioned_input" in result
        assert "metadata" in result
        assert "ambiguity_score" in result["metadata"]
        assert "domain" in result["metadata"]
        
        await plugin.shutdown()
    
    async def test_monitor_response(self, monkeypatch):
        """Test monitor response."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        await plugin.initialize()
        
        result = await plugin.monitor_response(
            session_id="test-session",
            response="Python is a programming language.",
            metadata={"domain": "ai"}
        )
        
        assert "metrics" in result
        assert "intervention" in result
        assert "anchors" in result
        assert "contradictions" in result
        
        await plugin.shutdown()
    
    async def test_get_session_metrics(self, monkeypatch):
        """Test getting session metrics."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        await plugin.initialize()
        
        # Add some metrics
        from src.components.coherence_monitor import CoherenceMetrics
        metrics = CoherenceMetrics(
            session_id="test-session",
            turn_number=1,
            delta_g=0.5,
            drift_velocity=0.0,
            variance=0.5,
            continuity_score=0.8
        )
        await plugin._db_manager.store_metrics("test-session", metrics)
        
        # Retrieve
        retrieved = await plugin.get_session_metrics("test-session")
        assert len(retrieved) == 1
        
        await plugin.shutdown()
    
    async def test_close_session(self, monkeypatch):
        """Test closing a session."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        await plugin.initialize()

        # Add some data
        await plugin._db_manager.store_session("test-session")

        # Add an anchor first via extract_anchors
        await plugin._session_anchoring.extract_anchors(
            session_id="test-session",
            text="Test anchor fact is important to remember."
        )

        # Verify anchor was added
        anchors_before = plugin._session_anchoring.get_anchors("test-session")
        assert len(anchors_before) > 0

        # Close
        await plugin.close_session("test-session")

        # Anchors should be cleared
        anchors = await plugin.get_session_anchors("test-session")
        assert len(anchors) == 0

        await plugin.shutdown()
    
    async def test_reload_config(self, monkeypatch):
        """Test hot config reload."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        await plugin.initialize()
        
        original_mode = plugin.config.mode
        
        # Reload
        await plugin.reload_config()
        
        # Config should be reloaded
        assert plugin.config is not None
        
        await plugin.shutdown()
    
    def test_get_plugin_singleton(self):
        """Test get_plugin returns singleton."""
        import src
        
        # Reset singleton
        src._plugin_instance = None
        
        plugin1 = get_plugin()
        plugin2 = get_plugin()
        
        assert plugin1 is plugin2
    
    async def test_initialize_plugin(self, monkeypatch):
        """Test initialize_plugin helper."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        import src

        # Reset singleton
        src._plugin_instance = None

        # Create a fresh plugin with mock config
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False

        src._plugin_instance = plugin
        await plugin.initialize()

        assert plugin is not None
        assert plugin._initialized is True

        await plugin.shutdown()
    
    async def test_circuit_breaker(self, monkeypatch):
        """Test circuit breaker behavior."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "true")
        plugin = BrainGuardPlugin()
        plugin.config.testing.mock_embeddings = True
        plugin.config.storage.connection_string = ":memory:"
        plugin.config.dashboard.enabled = False
        plugin.config.latency.max_ms = 1  # Very low to trigger circuit breaker

        await plugin.initialize()
        
        # This should trigger circuit breaker
        result = await plugin.preprocess_message(
            session_id="test",
            user_message="Hello"
        )
        
        # Should still return a result
        assert "conditioned_input" in result
        
        await plugin.shutdown()
