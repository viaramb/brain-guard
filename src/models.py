"""Shared models for Brain Guard components."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import numpy as np


@dataclass
class Contradiction:
    """Detected contradiction between anchors."""
    anchor_id: str
    anchor_text: str
    new_text: str
    similarity: float
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "anchor_text": self.anchor_text,
            "new_text": self.new_text,
            "similarity": round(self.similarity, 4),
            "confidence": round(self.confidence, 4)
        }


@dataclass
class Anchor:
    """A session anchor (fact, procedure, context, or temporal)."""
    id: str
    session_id: str
    text: str
    anchor_type: str  # factual, procedural, contextual, temporal
    confidence: float
    timestamp: float
    is_active: bool = True
    reference_count: int = 0
    embedding: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "text": self.text,
            "anchor_type": self.anchor_type,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "is_active": self.is_active,
            "reference_count": self.reference_count
        }


@dataclass
class Metrics:
    """Coherence metrics for a session."""
    session_id: str
    delta_g: float = 0.0  # Semantic drift
    drift_velocity: float = 0.0  # Rate of drift
    variance: float = 0.0  # Response variance
    continuity_score: float = 1.0  # Session continuity
    ambiguity_score: float = 0.0  # Input ambiguity
    processing_time_ms: float = 0.0  # Processing time
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "delta_g": round(self.delta_g, 4),
            "drift_velocity": round(self.drift_velocity, 4),
            "variance": round(self.variance, 4),
            "continuity_score": round(self.continuity_score, 4),
            "ambiguity_score": round(self.ambiguity_score, 4),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "timestamp": self.timestamp
        }


class InterventionType(Enum):
    """Types of interventions."""
    SILENT = "silent"
    FLAG = "flag"
    REGENERATE = "regenerate"
    FALLBACK = "fallback"
    HALT = "halt"


class InterventionPriority(Enum):
    """Priority levels for interventions."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Intervention:
    """Intervention decision."""
    type: InterventionType
    priority: InterventionPriority
    reason: str
    metrics_snapshot: Dict[str, Any]
    message: Optional[str] = None
    action_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "priority": self.priority.name,
            "reason": self.reason,
            "metrics": self.metrics_snapshot,
            "message": self.message,
            "action_required": self.action_required
        }
