"""Brain Guard Plugin - Main entry point for OpenClaw integration."""

import os
import asyncio
import logging
from typing import Any, Optional, Dict, List
from contextlib import asynccontextmanager

from .utils.config import Config, ConfigLoader
from .utils.embedding_service import EmbeddingService, MockEmbeddingService, create_embedding_service
from .utils.validation import (
    validate_session_id,
    validate_message,
    validate_context,
    validate_response,
    ValidationError
)
from .components.preprocessor import Preprocessor
from .components.coherence_monitor import CoherenceMonitor
from .components.threshold_engine import ThresholdEngine
from .components.session_anchoring import SessionAnchoring
from .components.domain_detector import DomainDetector
from .database.db_manager import DatabaseManager
from .api.dashboard import DashboardServer

logger = logging.getLogger(__name__)


class BrainGuardPlugin:
    """
    Main Brain Guard plugin implementing SCFL-Quad coherence monitoring.
    
    This plugin hooks into OpenClaw's message flow to provide:
    - Preprocessing (Layer 1): Input conditioning and ambiguity scoring
    - Coherence monitoring (Layer 3): Real-time ΔG, Vd, σ²c calculation
    - Threshold evaluation (Layer 4): Intervention decisions
    - Session anchoring: Track facts and detect contradictions
    - Domain detection: Auto-detect conversation domains
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Brain Guard plugin.
        
        Args:
            config_path: Path to configuration file. If None, uses default locations.
        """
        self._enabled = self._check_enabled()
        self.config: Config = ConfigLoader.load(config_path)
        
        # Core components
        self._embedding_service: Optional[EmbeddingService] = None
        self._preprocessor: Optional[Preprocessor] = None
        self._coherence_monitor: Optional[CoherenceMonitor] = None
        self._threshold_engine: Optional[ThresholdEngine] = None
        self._session_anchoring: Optional[SessionAnchoring] = None
        self._domain_detector: Optional[DomainDetector] = None
        self._db_manager: Optional[DatabaseManager] = None
        self._dashboard: Optional[DashboardServer] = None
        
        self._initialized = False
        self._shutdown_event = asyncio.Event()
        
    def _check_enabled(self) -> bool:
        """Check if plugin is enabled via environment variable."""
        env_var = os.environ.get("BRAIN_GUARD_ENABLED", "").lower()
        return env_var in ("true", "1", "yes", "on")
    
    @property
    def enabled(self) -> bool:
        """Whether the plugin is enabled."""
        return self._enabled and self.config.enabled
    
    async def initialize(self) -> None:
        """Initialize all plugin components."""
        if not self.enabled:
            logger.info("Brain Guard is disabled. Set BRAIN_GUARD_ENABLED=true to enable.")
            return
            
        if self._initialized:
            return
            
        logger.info("Initializing Brain Guard plugin...")
        
        # Initialize embedding service
        if self.config.testing.mock_embeddings:
            self._embedding_service = MockEmbeddingService(
                dimensions=self.config.embedding.dimensions
            )
        else:
            self._embedding_service = create_embedding_service(
                provider=self.config.embedding.provider,
                model=self.config.embedding.model,
                dimensions=self.config.embedding.dimensions,
                cache_enabled=self.config.embedding.cache_enabled,
                cache_ttl_seconds=self.config.embedding.cache_ttl_seconds
            )
        
        # Initialize database
        self._db_manager = DatabaseManager(
            storage_type=self.config.storage.type,
            connection_string=self.config.storage.connection_string
        )
        await self._db_manager.initialize()
        
        # Initialize components
        self._domain_detector = DomainDetector()
        
        self._session_anchoring = SessionAnchoring(
            max_anchors=self.config.anchoring.max_anchors,
            contradiction_check=self.config.anchoring.contradiction_check,
            contradiction_threshold=self.config.anchoring.contradiction_threshold
        )
        
        self._preprocessor = Preprocessor(
            embedding_service=self._embedding_service,
            ambiguity_threshold=self.config.thresholds.ambiguity,
            session_anchoring=self._session_anchoring
        )
        
        self._coherence_monitor = CoherenceMonitor(
            embedding_service=self._embedding_service,
            window_size=5,
            variance_threshold=self.config.thresholds.variance_collapse
        )
        
        self._threshold_engine = ThresholdEngine(
            thresholds=self.config.thresholds,
            mode=self.config.mode,
            interventions_config=self.config.interventions
        )
        
        # Initialize dashboard if enabled
        if self.config.dashboard.enabled:
            self._dashboard = DashboardServer(
                host=self.config.dashboard.host,
                port=self.config.dashboard.port,
                db_manager=self._db_manager,
                auth_required=self.config.dashboard.auth_required,
                auth_token=self.config.dashboard.auth_token,
                cors_origins=self.config.dashboard.cors_origins
            )
            await self._dashboard.start()
        
        self._initialized = True
        logger.info("Brain Guard plugin initialized successfully")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the plugin."""
        if not self._initialized:
            return
            
        logger.info("Shutting down Brain Guard plugin...")
        self._shutdown_event.set()
        
        if self._dashboard:
            await self._dashboard.stop()
            
        if self._db_manager:
            await self._db_manager.close()
            
        self._initialized = False
        logger.info("Brain Guard plugin shutdown complete")
    
    async def preprocess_message(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Preprocess user message (Layer 1 - Input Conditioning).
        
        Args:
            session_id: Unique session identifier
            user_message: Raw user input
            context: Optional session context
            
        Returns:
            Dictionary containing conditioned input and metadata
        """
        if not self.enabled or not self._initialized:
            return {"conditioned_input": user_message, "metadata": {}}
        
        # Validate inputs
        try:
            validate_session_id(session_id)
            validate_message(user_message)
            validate_context(context)
        except ValidationError as e:
            logger.warning(f"Input validation failed: {e}")
            return {"conditioned_input": user_message, "metadata": {"validation_error": str(e)}}
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Detect domain
            domain = self._domain_detector.detect_domain(user_message)
            
            # Preprocess the message
            result = await self._preprocessor.process(
                session_id=session_id,
                message=user_message,
                domain=domain
            )
            
            # Store session metadata
            await self._db_manager.store_session(
                session_id=session_id,
                domain=domain,
                metadata=context or {}
            )
            
            # Calculate processing time
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Check circuit breaker
            if processing_time > self.config.latency.max_ms:
                logger.warning(f"Preprocessing exceeded latency budget: {processing_time:.2f}ms")
                if self._should_circuit_break():
                    return {"conditioned_input": user_message, "metadata": {"circuit_broken": True}}
            
            result["metadata"]["processing_time_ms"] = processing_time
            result["metadata"]["domain"] = domain
            
            return result
            
        except Exception as e:
            logger.error(f"Error in preprocess_message: {e}")
            return {"conditioned_input": user_message, "metadata": {"error": "Internal processing error"}}
    
    async def monitor_response(
        self,
        session_id: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Monitor LLM response (Layer 3 - Coherence Monitor + Layer 4 - Threshold Engine).
        
        Args:
            session_id: Unique session identifier
            response: LLM response text
            metadata: Optional metadata from preprocessing
            
        Returns:
            Dictionary containing metrics and intervention decisions
        """
        if not self.enabled or not self._initialized:
            return {"metrics": {}, "intervention": None}
        
        # Validate inputs
        try:
            validate_session_id(session_id)
            if response:
                validate_response(response)
            validate_context(metadata)
        except ValidationError as e:
            logger.warning(f"Input validation failed: {e}")
            return {"metrics": {}, "intervention": None, "validation_error": str(e)}
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get previous responses for this session
            session_history = await self._db_manager.get_session_history(session_id)
            
            # Calculate coherence metrics
            metrics = await self._coherence_monitor.calculate_metrics(
                session_id=session_id,
                current_response=response,
                history=session_history
            )
            
            # Extract and store anchors
            anchors = await self._session_anchoring.extract_anchors(
                session_id=session_id,
                text=response
            )
            
            # Check for contradictions
            contradictions = []
            if self.config.anchoring.contradiction_check:
                contradictions = await self._session_anchoring.check_contradictions(
                    session_id=session_id,
                    new_text=response
                )
            
            # Evaluate thresholds and determine intervention
            intervention = self._threshold_engine.evaluate(
                metrics=metrics,
                contradictions=contradictions,
                domain=metadata.get("domain", "general") if metadata else "general"
            )
            
            # Store metrics with timing
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            metrics.processing_time_ms = processing_time
            
            await self._db_manager.store_metrics(
                session_id=session_id,
                metrics=metrics
            )
            
            # Store intervention if triggered
            if intervention:
                await self._db_manager.store_intervention(
                    session_id=session_id,
                    intervention=intervention,
                    metrics=metrics
                )
            
            # Check latency budget
            if processing_time > self.config.latency.max_ms:
                logger.warning(f"Monitoring exceeded latency budget: {processing_time:.2f}ms")
            
            # Build response with timing metadata
            response_data = {
                "metrics": metrics.to_dict(),
                "intervention": intervention.to_dict() if intervention else None,
                "anchors": [a.to_dict() for a in anchors],
                "contradictions": [c.to_dict() for c in contradictions],
                "timing": {
                    "total_processing_time_ms": round(processing_time, 4),
                    "coherence_analysis_time_ms": round(metrics.processing_time_ms, 4),
                    "embedding_time_ms": round(metrics.embedding_time_ms, 4)
                }
            }
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error in monitor_response: {e}")
            return {"metrics": {}, "intervention": None, "error": str(e)}
    
    def _should_circuit_break(self) -> bool:
        """Check if circuit breaker should open based on recent latency."""
        # Simplified circuit breaker - in production, track request statistics
        return False
    
    async def get_session_metrics(
        self,
        session_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Get historical metrics for a session."""
        if not self._initialized or not self._db_manager:
            return []
        return await self._db_manager.get_metrics(session_id, start_time, end_time)
    
    async def get_session_anchors(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all anchors for a session."""
        if not self._initialized or not self._session_anchoring:
            return []
        anchors = self._session_anchoring.get_anchors(session_id)
        return [a.to_dict() for a in anchors]
    
    async def close_session(self, session_id: str) -> None:
        """Close a session and cleanup resources."""
        if not self._initialized:
            return

        if self._session_anchoring:
            self._session_anchoring.clear_session(session_id)

        await self._db_manager.update_session_status(
            session_id=session_id,
            status="closed"
        )
    
    async def reload_config(self) -> None:
        """Hot-reload configuration."""
        logger.info("Reloading Brain Guard configuration...")
        self.config = ConfigLoader.load()
        
        # Reinitialize components that depend on config
        if self._threshold_engine:
            self._threshold_engine.update_config(
                thresholds=self.config.thresholds,
                mode=self.config.mode
            )
        
        logger.info("Configuration reloaded successfully")


# Singleton instance for OpenClaw integration
_plugin_instance: Optional[BrainGuardPlugin] = None


def get_plugin(config_path: Optional[str] = None) -> BrainGuardPlugin:
    """Get or create the singleton plugin instance."""
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = BrainGuardPlugin(config_path)
    return _plugin_instance


async def initialize_plugin(config_path: Optional[str] = None) -> BrainGuardPlugin:
    """Initialize and return the plugin instance."""
    plugin = get_plugin(config_path)
    await plugin.initialize()
    return plugin
