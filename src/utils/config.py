"""Configuration management for Brain Guard."""

import os
import json
import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class LatencyConfig:
    """Latency budget and circuit breaker settings."""
    target_ms: int = 50
    max_ms: int = 100
    circuit_breaker_threshold: float = 0.95
    circuit_breaker_timeout_ms: int = 5000
    async_metrics: bool = True


@dataclass
class ThresholdConfig:
    """SCFL-Quad threshold values."""
    drift_warning: float = 0.65
    rupture_alert: float = 0.85
    drift_velocity: float = 0.10
    variance_collapse: float = 0.02
    recoverability: float = 0.30
    ambiguity: float = 0.70


@dataclass
class MonitoringConfig:
    """Monitoring level and escalation settings."""
    default_level: str = "light"
    escalation_turns: int = 10
    high_stakes_keywords: List[str] = field(default_factory=lambda: [
        "medical", "health", "diagnosis", "prescription",
        "legal", "contract", "agreement", "liability",
        "financial", "investment", "tax", "account",
        "security", "password", "credential", "private key"
    ])
    deescalation_turns: int = 5


@dataclass
class EmbeddingConfig:
    """Embedding model configuration."""
    provider: str = "local"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_size: int = 1000
    fallback_to_string_sim: bool = True
    api_key: str = ""
    local_model: str = "all-MiniLM-L6-v2"


@dataclass
class AnchoringConfig:
    """Session anchor extraction and management."""
    enabled: bool = True
    max_anchors: int = 50
    contradiction_check: bool = True
    contradiction_threshold: float = 0.85
    anchor_types: List[str] = field(default_factory=lambda: [
        "factual", "procedural", "contextual", "temporal"
    ])


@dataclass
class InterventionsConfig:
    """Intervention behavior settings."""
    auto_regenerate: bool = False
    max_regenerations: int = 2
    user_confirmation_for_halt: bool = True
    fallback_message: str = "I'm having trouble maintaining coherence. Let me try a more careful approach."


@dataclass
class StorageConfig:
    """Database and persistence settings."""
    type: str = "sqlite"
    connection_string: str = "~/.openclaw/brain_guard.db"
    retention_days: int = 30
    aggregation_retention_days: int = 365
    batch_size: int = 100
    write_interval_ms: int = 1000
    pool_size: int = 5
    max_overflow: int = 10


@dataclass
class DashboardConfig:
    """Dashboard API and UI settings."""
    enabled: bool = True
    port: int = 8080
    host: str = "127.0.0.1"
    auth_required: bool = True
    auth_token: str = ""
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])
    max_sessions_list: int = 100


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "info"
    log_interventions: bool = True
    log_metrics: bool = False
    log_file: str = ""
    format: str = "text"
    output: str = "stdout"


@dataclass
class TestingConfig:
    """Testing and calibration settings."""
    mock_embeddings: bool = False
    calibration_mode: bool = False
    a_b_test_enabled: bool = False
    mock_database: bool = False


@dataclass
class Config:
    """Complete Brain Guard configuration."""
    enabled: bool = True
    mode: str = "adaptive"
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    anchoring: AnchoringConfig = field(default_factory=AnchoringConfig)
    interventions: InterventionsConfig = field(default_factory=InterventionsConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    testing: TestingConfig = field(default_factory=TestingConfig)


class ConfigLoader:
    """Load and validate configuration from files and environment."""
    
    DEFAULT_PATHS = [
        "./config/brain-guard.yml",
        "./config/brain-guard.yaml",
        "~/.openclaw/brain-guard.yml",
        "~/.openclaw/brain-guard.yaml",
        "/etc/openclaw/brain-guard.yml",
    ]
    
    SCHEMA_PATH = "./config/schema.json"
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> Config:
        """
        Load configuration from file.
        
        Args:
            config_path: Specific path to config file. If None, searches default locations.
            
        Returns:
            Config object with loaded settings
        """
        # Determine config file path
        if config_path:
            paths = [config_path]
        else:
            paths = cls.DEFAULT_PATHS
            # Also check environment variable
            env_path = os.environ.get("BRAIN_GUARD_CONFIG_PATH")
            if env_path:
                paths.insert(0, env_path)
        
        # Find and load config file
        config_data = {}
        for path in paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                with open(expanded_path, 'r') as f:
                    if path.endswith('.json'):
                        config_data = json.load(f)
                    else:
                        config_data = yaml.safe_load(f)
                break
        
        # Apply environment variable overrides
        config_data = cls._apply_env_overrides(config_data)
        
        # Build Config object
        return cls._build_config(config_data)
    
    @classmethod
    def _apply_env_overrides(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config."""
        # BRAIN_GUARD_ENABLED
        env_enabled = os.environ.get("BRAIN_GUARD_ENABLED")
        if env_enabled is not None:
            config["enabled"] = env_enabled.lower() in ("true", "1", "yes", "on")
        
        # BRAIN_GUARD_MODE
        env_mode = os.environ.get("BRAIN_GUARD_MODE")
        if env_mode:
            config["mode"] = env_mode
        
        # BRAIN_GUARD_DB_URL
        env_db = os.environ.get("BRAIN_GUARD_DB_URL")
        if env_db:
            if "storage" not in config:
                config["storage"] = {}
            config["storage"]["connection_string"] = env_db
        
        # BRAIN_GUARD_DASHBOARD_ENABLED
        env_dashboard = os.environ.get("BRAIN_GUARD_DASHBOARD_ENABLED")
        if env_dashboard is not None:
            if "dashboard" not in config:
                config["dashboard"] = {}
            config["dashboard"]["enabled"] = env_dashboard.lower() in ("true", "1", "yes", "on")
        
        # BRAIN_GUARD_DASHBOARD_PORT
        env_port = os.environ.get("BRAIN_GUARD_DASHBOARD_PORT")
        if env_port:
            if "dashboard" not in config:
                config["dashboard"] = {}
            config["dashboard"]["port"] = int(env_port)
        
        # BRAIN_GUARD_LOG_LEVEL
        env_log = os.environ.get("BRAIN_GUARD_LOG_LEVEL")
        if env_log:
            if "logging" not in config:
                config["logging"] = {}
            config["logging"]["level"] = env_log
        
        return config
    
    @classmethod
    def _build_config(cls, data: Dict[str, Any]) -> Config:
        """Build Config object from dictionary."""
        return Config(
            enabled=data.get("enabled", True),
            mode=data.get("mode", "adaptive"),
            latency=LatencyConfig(**data.get("latency", {})),
            thresholds=ThresholdConfig(**data.get("thresholds", {})),
            monitoring=MonitoringConfig(**data.get("monitoring", {})),
            embedding=EmbeddingConfig(**data.get("embedding", {})),
            anchoring=AnchoringConfig(**data.get("anchoring", {})),
            interventions=InterventionsConfig(**data.get("interventions", {})),
            storage=StorageConfig(**data.get("storage", {})),
            dashboard=DashboardConfig(**data.get("dashboard", {})),
            logging=LoggingConfig(**data.get("logging", {})),
            testing=TestingConfig(**data.get("testing", {}))
        )
    
    @classmethod
    def validate(cls, config_data: Dict[str, Any]) -> bool:
        """
        Validate configuration against JSON schema.
        
        Args:
            config_data: Configuration dictionary to validate
            
        Returns:
            True if valid, raises exception otherwise
        """
        try:
            from jsonschema import validate
            
            schema_path = Path(cls.SCHEMA_PATH).expanduser()
            if not schema_path.exists():
                # Try relative to package
                schema_path = Path(__file__).parent.parent.parent / "config" / "schema.json"
            
            with open(schema_path, 'r') as f:
                schema = json.load(f)
            
            validate(instance=config_data, schema=schema)
            return True
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")
