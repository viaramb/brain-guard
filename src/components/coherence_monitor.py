"""Coherence Monitor component - Layer 3: CFM (Coherence Field Monitor)."""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

from ..utils.embedding_service import EmbeddingService, EmbeddingTimingMetrics
from ..utils.validation import validate_session_id, validate_message, ValidationError
from ..metrics import get_metrics_exporter

logger = logging.getLogger(__name__)


@dataclass
class CoherenceMetrics:
    """Coherence metrics for a single response."""
    session_id: str
    turn_number: int
    delta_g: float  # Coherence deformation
    drift_velocity: float  # Vd
    variance: float  # σ²
    continuity_score: float  # CS
    processing_time_ms: float = 0.0  # Total coherence monitor processing time
    embedding_time_ms: float = 0.0  # Embedding generation time
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "delta_g": round(self.delta_g, 4),
            "drift_velocity": round(self.drift_velocity, 4),
            "variance": round(self.variance, 4),
            "continuity_score": round(self.continuity_score, 4),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "embedding_time_ms": round(self.embedding_time_ms, 2),
            "timestamp": self.timestamp
        }


class CoherenceMonitor:
    """
    Layer 3: Coherence Field Monitor (CFM)
    
    Responsibilities:
    - Calculate ΔG (coherence deformation)
    - Calculate Vd (drift velocity)
    - Calculate σ²c (variance collapse)
    - Calculate overall continuity score
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        window_size: int = 5,
        variance_threshold: float = 0.02
    ):
        self.embedding_service = embedding_service
        self.window_size = window_size
        self.variance_threshold = variance_threshold
        
        # Session state
        self._session_embeddings: Dict[str, deque] = {}
        self._session_metrics: Dict[str, List[CoherenceMetrics]] = {}
        self._turn_counters: Dict[str, int] = {}
    
    async def calculate_metrics(
        self,
        session_id: str,
        current_response: str,
        history: List[Dict[str, Any]]
    ) -> CoherenceMetrics:
        """
        Calculate coherence metrics for a response.
        
        Args:
            session_id: Unique session identifier
            current_response: Current LLM response
            history: Previous session history
            
        Returns:
            CoherenceMetrics object
        """
        import time
        start_time = time.perf_counter()
        
        # Validate inputs
        validate_session_id(session_id)
        if not current_response or not isinstance(current_response, str):
            raise ValidationError("current_response", "Must be a non-empty string")
        if len(current_response) > 10000:
            raise ValidationError("current_response", "Exceeds maximum length of 10000 characters")
        if '\x00' in current_response:
            raise ValidationError("current_response", "Contains null bytes which are not allowed")
        
        # Initialize session state if needed
        if session_id not in self._session_embeddings:
            self._session_embeddings[session_id] = deque(maxlen=self.window_size)
            self._session_metrics[session_id] = []
            self._turn_counters[session_id] = 0
        
        self._turn_counters[session_id] += 1
        turn_number = self._turn_counters[session_id]
        
        # Get embedding for current response with timing
        current_embedding, embedding_timing = await self.embedding_service.embed(current_response)
        
        # Calculate metrics
        delta_g = self._calculate_delta_g(session_id, current_embedding)
        drift_velocity = self._calculate_drift_velocity(session_id, delta_g)
        variance = self._calculate_variance(session_id, current_embedding)
        continuity_score = self._calculate_continuity_score(
            delta_g, drift_velocity, variance
        )
        
        # Store embedding for future comparison
        self._session_embeddings[session_id].append(current_embedding)
        
        # Calculate processing time
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Create metrics object with timing information
        metrics = CoherenceMetrics(
            session_id=session_id,
            turn_number=turn_number,
            delta_g=delta_g,
            drift_velocity=drift_velocity,
            variance=variance,
            continuity_score=continuity_score,
            processing_time_ms=processing_time_ms,
            embedding_time_ms=embedding_timing.embedding_time_ms
        )
        
        # Store metrics history
        self._session_metrics[session_id].append(metrics)
        
        # Emit Prometheus metrics
        try:
            exporter = get_metrics_exporter()
            exporter.emit_coherence_metrics(
                session_id=session_id,
                delta_g=delta_g,
                drift_velocity=drift_velocity,
                variance=variance,
                continuity_score=continuity_score,
                processing_time_ms=processing_time_ms
            )
        except Exception as e:
            logger.warning(f"Failed to emit coherence metrics: {e}")
        
        return metrics
    
    def _calculate_delta_g(
        self,
        session_id: str,
        current_embedding: np.ndarray
    ) -> float:
        """
        Calculate ΔG (coherence deformation).
        
        ΔG_i = 1 - cos_similarity(embedding(s_i), embedding(s_{i-1}))
        
        Args:
            session_id: Session identifier
            current_embedding: Current response embedding
            
        Returns:
            Delta G value in range [0, 1]
        """
        embeddings = self._session_embeddings.get(session_id, deque())
        
        if not embeddings:
            # First message - no previous to compare
            return 0.0
        
        previous_embedding = embeddings[-1]
        similarity = self.embedding_service.cosine_similarity(
            current_embedding,
            previous_embedding
        )
        
        # Convert similarity to distance (0 = identical, 1 = orthogonal)
        delta_g = 1.0 - similarity
        
        # Clamp to valid range
        return max(0.0, min(1.0, delta_g))
    
    def _calculate_drift_velocity(
        self,
        session_id: str,
        current_delta_g: float
    ) -> float:
        """
        Calculate Vd (drift velocity).
        
        Vd(i) = ΔG_i - ΔG_{i-1}
        
        Args:
            session_id: Session identifier
            current_delta_g: Current delta G value
            
        Returns:
            Drift velocity (positive = accelerating drift)
        """
        metrics = self._session_metrics.get(session_id, [])
        
        if not metrics:
            return 0.0
        
        previous_delta_g = metrics[-1].delta_g
        return current_delta_g - previous_delta_g
    
    def _calculate_variance(
        self,
        session_id: str,
        current_embedding: np.ndarray
    ) -> float:
        """
        Calculate σ²c (variance collapse).
        
        σ²c = Var(embedding_window(s_{i-k}...s_i))
        
        Args:
            session_id: Session identifier
            current_embedding: Current response embedding
            
        Returns:
            Variance value
        """
        embeddings = self._session_embeddings.get(session_id, deque())
        
        if not embeddings:
            return 1.0  # Maximum variance for single point
        
        # Include current embedding in window
        window = list(embeddings) + [current_embedding]
        
        if len(window) < 2:
            return 1.0
        
        # Calculate variance across embedding dimensions
        # Stack embeddings into matrix
        matrix = np.stack(window)
        
        # Calculate mean variance across all dimensions
        variances = np.var(matrix, axis=0)
        mean_variance = float(np.mean(variances))
        
        return mean_variance
    
    def _calculate_continuity_score(
        self,
        delta_g: float,
        drift_velocity: float,
        variance: float
    ) -> float:
        """
        Calculate overall continuity score.
        
        CS = weighted_average(ΔG, Vd, σ²c)
        
        Args:
            delta_g: Coherence deformation
            drift_velocity: Drift velocity
            variance: Variance
            
        Returns:
            Continuity score in range [0, 1]
        """
        # Normalize components
        # delta_g: 0 = perfect, 1 = rupture
        # drift_velocity: we care about magnitude and direction
        # variance: low variance = repetition/collapse
        
        # Delta G component (inverted, so 1 = perfect)
        delta_g_component = 1.0 - delta_g
        
        # Drift velocity component (penalize positive acceleration)
        if drift_velocity > 0:
            drift_component = max(0.0, 1.0 - drift_velocity * 5)
        else:
            drift_component = 1.0  # Negative drift is stabilizing
        
        # Variance component (penalize both very low and very high)
        # Optimal variance is in middle range
        if variance < self.variance_threshold:
            # Variance collapse
            variance_component = variance / self.variance_threshold
        elif variance > 1.0:
            variance_component = 0.5
        else:
            variance_component = 1.0
        
        # Weighted average
        weights = {
            "delta_g": 0.5,
            "drift": 0.3,
            "variance": 0.2
        }
        
        continuity_score = (
            weights["delta_g"] * delta_g_component +
            weights["drift"] * drift_component +
            weights["variance"] * variance_component
        )
        
        return max(0.0, min(1.0, continuity_score))
    
    def get_session_history(self, session_id: str) -> List[CoherenceMetrics]:
        """Get metrics history for a session."""
        return self._session_metrics.get(session_id, [])
    
    def clear_session(self, session_id: str) -> None:
        """Clear session state."""
        if session_id in self._session_embeddings:
            del self._session_embeddings[session_id]
        if session_id in self._session_metrics:
            del self._session_metrics[session_id]
        if session_id in self._turn_counters:
            del self._turn_counters[session_id]
    
    def detect_variance_collapse(self, session_id: str) -> bool:
        """
        Detect if session is experiencing variance collapse.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if variance collapse detected
        """
        metrics = self._session_metrics.get(session_id, [])
        
        if len(metrics) < 3:
            return False
        
        # Check recent variance values
        recent_variances = [m.variance for m in metrics[-3:]]
        avg_variance = sum(recent_variances) / len(recent_variances)
        
        return avg_variance < self.variance_threshold
    
    def detect_accelerating_drift(self, session_id: str) -> bool:
        """
        Detect if session is experiencing accelerating drift.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if accelerating drift detected
        """
        metrics = self._session_metrics.get(session_id, [])
        
        if len(metrics) < 2:
            return False
        
        # Check if recent velocities are positive and increasing
        recent_velocities = [m.drift_velocity for m in metrics[-3:]]
        
        # At least 2 positive velocities
        positive_count = sum(1 for v in recent_velocities if v > 0)
        return positive_count >= 2
