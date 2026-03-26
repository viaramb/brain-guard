"""Unit tests for Configuration module."""

import os
import pytest
import tempfile
from pathlib import Path

from src.utils.config import ConfigLoader, Config, ThresholdConfig


@pytest.fixture
def temp_config_file():
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write("""
enabled: true
mode: strict
thresholds:
  drift_warning: 0.5
  rupture_alert: 0.8
embedding:
  provider: mock
  dimensions: 256
""")
        path = f.name
    
    yield path
    
    # Cleanup
    os.unlink(path)


@pytest.mark.unit
class TestConfigLoader:
    """Tests for ConfigLoader."""
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        config = ConfigLoader.load()
        
        assert isinstance(config, Config)
        assert config.enabled is True
        assert config.mode in ["silent", "warn", "strict", "adaptive"]
    
    def test_load_from_file(self, temp_config_file):
        """Test loading from specific file."""
        config = ConfigLoader.load(temp_config_file)
        
        assert config.mode == "strict"
        assert config.thresholds.drift_warning == 0.5
        assert config.embedding.provider == "mock"
        assert config.embedding.dimensions == 256
    
    def test_env_override_enabled(self, monkeypatch):
        """Test BRAIN_GUARD_ENABLED env override."""
        monkeypatch.setenv("BRAIN_GUARD_ENABLED", "false")
        
        config = ConfigLoader.load()
        assert config.enabled is False
    
    def test_env_override_mode(self, monkeypatch):
        """Test BRAIN_GUARD_MODE env override."""
        monkeypatch.setenv("BRAIN_GUARD_MODE", "warn")
        
        config = ConfigLoader.load()
        assert config.mode == "warn"
    
    def test_env_override_db_url(self, monkeypatch):
        """Test BRAIN_GUARD_DB_URL env override."""
        monkeypatch.setenv("BRAIN_GUARD_DB_URL", "postgresql://localhost/db")
        
        config = ConfigLoader.load()
        assert config.storage.connection_string == "postgresql://localhost/db"
    
    def test_env_override_port(self, monkeypatch):
        """Test BRAIN_GUARD_DASHBOARD_PORT env override."""
        monkeypatch.setenv("BRAIN_GUARD_DASHBOARD_PORT", "9090")
        
        config = ConfigLoader.load()
        assert config.dashboard.port == 9090
    
    def test_env_override_log_level(self, monkeypatch):
        """Test BRAIN_GUARD_LOG_LEVEL env override."""
        monkeypatch.setenv("BRAIN_GUARD_LOG_LEVEL", "debug")
        
        config = ConfigLoader.load()
        assert config.logging.level == "debug"
    
    def test_build_config(self):
        """Test building config from dictionary."""
        data = {
            "enabled": False,
            "mode": "silent",
            "thresholds": {
                "drift_warning": 0.4
            }
        }
        
        config = ConfigLoader._build_config(data)
        
        assert config.enabled is False
        assert config.mode == "silent"
        assert config.thresholds.drift_warning == 0.4
        # Default values preserved
        assert config.thresholds.rupture_alert == 0.85
    
    def test_threshold_config_defaults(self):
        """Test ThresholdConfig defaults."""
        config = ThresholdConfig()
        
        assert config.drift_warning == 0.65
        assert config.rupture_alert == 0.85
        assert config.drift_velocity == 0.10
        assert config.variance_collapse == 0.02
        assert config.recoverability == 0.30
    
    def test_config_nested_defaults(self):
        """Test that nested configs have defaults."""
        config = Config()
        
        assert config.latency.target_ms == 50
        assert config.monitoring.default_level == "light"
        assert config.anchoring.max_anchors == 50
        assert config.dashboard.enabled is True
    
    def test_enabled_variations(self, monkeypatch):
        """Test various enabled env value variations."""
        for value in ["true", "1", "yes", "on"]:
            monkeypatch.setenv("BRAIN_GUARD_ENABLED", value)
            config = ConfigLoader.load()
            assert config.enabled is True, f"Failed for value: {value}"
    
    def test_disabled_variations(self, monkeypatch):
        """Test various disabled env value variations."""
        for value in ["false", "0", "no", "off"]:
            monkeypatch.setenv("BRAIN_GUARD_ENABLED", value)
            config = ConfigLoader.load()
            assert config.enabled is False, f"Failed for value: {value}"
