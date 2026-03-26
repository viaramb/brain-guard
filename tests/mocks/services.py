"""Mock services for testing Brain Guard components."""

import numpy as np
from typing import List, Dict, Any, Optional


class MockEmbeddingService:
    """Mock embedding service for testing."""
    
    def __init__(self, dimensions: int = 128, cache_enabled: bool = False):
        self.dimensions = dimensions
        self._cache: Dict[str, np.ndarray] = {}
        self._cache_enabled = cache_enabled
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def embed(self, text: str) -> np.ndarray:
        """Generate deterministic mock embedding."""
        if self._cache_enabled and text in self._cache:
            self._cache_hits += 1
            return self._cache[text]
        
        self._cache_misses += 1
        
        # Generate deterministic embedding based on text hash
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(self.dimensions).astype(np.float32)
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        if self._cache_enabled:
            self._cache[text] = embedding
        
        return embedding
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot / (norm_a * norm_b))
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0
        
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._cache),
            "hit_rate": hit_rate
        }


class MockDatabaseManager:
    """Mock database manager for testing."""
    
    def __init__(self):
        self._sessions: Dict[str, Dict] = {}
        self._metrics: Dict[str, List[Dict]] = {}
        self._interventions: Dict[str, List[Dict]] = {}
    
    async def initialize(self) -> None:
        """Initialize mock database."""
        pass
    
    async def close(self) -> None:
        """Close mock database."""
        pass
    
    async def store_session(
        self,
        session_id: str,
        domain: str = "general",
        metadata: Optional[Dict] = None
    ) -> None:
        """Store session."""
        self._sessions[session_id] = {
            "id": session_id,
            "domain": domain,
            "metadata": metadata or {},
            "status": "active"
        }
    
    async def update_session_status(
        self,
        session_id: str,
        status: str
    ) -> None:
        """Update session status."""
        if session_id in self._sessions:
            self._sessions[session_id]["status"] = status
    
    async def store_metrics(
        self,
        session_id: str,
        metrics: Any
    ) -> None:
        """Store metrics."""
        if session_id not in self._metrics:
            self._metrics[session_id] = []
        
        self._metrics[session_id].append(
            metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
        )
    
    async def get_metrics(
        self,
        session_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict]:
        """Get metrics for session."""
        return self._metrics.get(session_id, [])
    
    async def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get session summary."""
        if session_id not in self._sessions:
            return None
        
        metrics = self._metrics.get(session_id, [])
        
        return {
            "session_id": session_id,
            "total_turns": len(metrics),
            "avg_delta_g": sum(m.get("delta_g", 0) for m in metrics) / len(metrics) if metrics else 0,
            "avg_continuity_score": sum(m.get("continuity_score", 0) for m in metrics) / len(metrics) if metrics else 0
        }
    
    async def get_session_history(self, session_id: str) -> List[Dict]:
        """Get session history."""
        return self._metrics.get(session_id, [])
    
    async def get_recent_sessions(self, limit: int = 100) -> List[Dict]:
        """Get recent sessions."""
        sessions = list(self._sessions.values())
        return sessions[-limit:]
    
    async def get_dashboard_summary(self) -> Dict:
        """Get dashboard summary."""
        total_metrics = sum(len(m) for m in self._metrics.values())
        
        return {
            "total_sessions": len(self._sessions),
            "total_metrics": total_metrics,
            "active_sessions": sum(1 for s in self._sessions.values() if s.get("status") == "active")
        }
    
    async def store_intervention(
        self,
        session_id: str,
        intervention: Any,
        metrics: Any
    ) -> None:
        """Store intervention."""
        if session_id not in self._interventions:
            self._interventions[session_id] = []
        
        self._interventions[session_id].append({
            "intervention": intervention.to_dict() if hasattr(intervention, 'to_dict') else intervention,
            "metrics": metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
        })


class MockThresholdEngine:
    """Mock threshold engine for testing."""
    
    def __init__(self, thresholds=None, mode="adaptive"):
        self.thresholds = thresholds
        self.mode = mode
        self._interventions = []
    
    def evaluate(self, metrics, contradictions, domain="general"):
        """Evaluate metrics and return mock intervention."""
        from src.components.threshold_engine import Intervention, InterventionType, InterventionPriority
        
        # Simple mock logic
        if metrics.delta_g > 0.8:
            return Intervention(
                type=InterventionType.REGENERATE,
                priority=InterventionPriority.HIGH,
                reason="mock_high_drift",
                metrics_snapshot=metrics.to_dict(),
                action_required=True
            )
        
        return None
    
    def update_config(self, thresholds, mode):
        """Update configuration."""
        self.thresholds = thresholds
        self.mode = mode
    
    def reset_session(self, session_id):
        """Reset session."""
        pass


class MockCoherenceMonitor:
    """Mock coherence monitor for testing."""
    
    def __init__(self, embedding_service=None, window_size=5):
        self.embedding_service = embedding_service
        self.window_size = window_size
        self._metrics = []
    
    async def calculate_metrics(self, session_id, current_response, history):
        """Calculate mock metrics."""
        from src.components.coherence_monitor import CoherenceMetrics
        
        metrics = CoherenceMetrics(
            session_id=session_id,
            turn_number=len(self._metrics) + 1,
            delta_g=0.1,
            drift_velocity=0.0,
            variance=0.5,
            continuity_score=0.9
        )
        
        self._metrics.append(metrics)
        return metrics
    
    def get_session_history(self, session_id):
        """Get session history."""
        return self._metrics
    
    def clear_session(self, session_id):
        """Clear session."""
        self._metrics = []
    
    def detect_variance_collapse(self, session_id):
        """Detect variance collapse."""
        return False
    
    def detect_accelerating_drift(self, session_id):
        """Detect accelerating drift."""
        return False


class MockSessionAnchoring:
    """Mock session anchoring for testing."""
    
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service
        self._anchors = []
    
    async def extract_anchors(self, session_id, text):
        """Extract mock anchors."""
        from src.components.session_anchoring import Anchor
        import time
        
        anchor = Anchor(
            id=f"{session_id}_anchor_1",
            session_id=session_id,
            text=text[:50] if len(text) > 50 else text,
            anchor_type="factual",
            confidence=0.8,
            timestamp=time.time()
        )
        
        self._anchors.append(anchor)
        return [anchor]
    
    async def check_contradictions(self, session_id, new_text):
        """Check for contradictions."""
        return []
    
    async def get_relevant_anchors(self, session_id, query, top_k=3):
        """Get relevant anchors."""
        return self._anchors[:top_k]
    
    def get_anchors(self, session_id, anchor_type=None):
        """Get all anchors."""
        return self._anchors
    
    def clear_session(self, session_id):
        """Clear session."""
        self._anchors = []
