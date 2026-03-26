"""Preprocessor component - Layer 1: Input Conditioning."""

import re
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from ..utils.embedding_service import EmbeddingService
from .session_anchoring import SessionAnchoring

logger = logging.getLogger(__name__)


@dataclass
class PreprocessResult:
    """Result of preprocessing a message."""
    conditioned_input: str
    segments: List[str]
    ambiguity_score: float
    ambiguity_flags: List[str]
    constraints_injected: List[str]
    metadata: Dict[str, Any]
    processing_time_ms: float = 0.0


@dataclass
class PreprocessTimingMetrics:
    """Timing metrics for preprocessing operations."""
    segmentation_time_ms: float = 0.0
    ambiguity_calculation_time_ms: float = 0.0
    anchor_retrieval_time_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    timestamp: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "segmentation_time_ms": round(self.segmentation_time_ms, 4),
            "ambiguity_calculation_time_ms": round(self.ambiguity_calculation_time_ms, 4),
            "anchor_retrieval_time_ms": round(self.anchor_retrieval_time_ms, 4),
            "total_processing_time_ms": round(self.total_processing_time_ms, 4),
            "timestamp": self.timestamp
        }


class Preprocessor:
    """
    Layer 1: Input Conditioning
    
    Responsibilities:
    - Prompt segmentation into semantic units
    - Ambiguity scoring (0-1 scale)
    - Constraint injection based on session anchors
    - Operator tag extraction
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        ambiguity_threshold: float = 0.70,
        session_anchoring: Optional[SessionAnchoring] = None
    ):
        self.embedding_service = embedding_service
        self.ambiguity_threshold = ambiguity_threshold
        self.session_anchoring = session_anchoring
        
        # Ambiguity indicators
        self._vague_references = [
            r'\bit\b', r'\bthis\b', r'\bthat\b', r'\bthese\b', r'\bthose\b',
            r'\bhere\b', r'\bthere\b', r'\bthem\b', r'\bthey\b'
        ]
        self._uncertainty_markers = [
            r'\bmaybe\b', r'\bperhaps\b', r'\bpossibly\b', r'\bmight\b',
            r'\bcould be\b', r'\bsort of\b', r'\bkind of\b'
        ]
        self._missing_context = [
            r'^\?', r'\?$', r'\bwhat\b.*\?', r'\bhow\b.*\?', 
            r'\bwhy\b.*\?', r'\bwhen\b.*\?', r'\bwhere\b.*\?'
        ]
    
    def _sanitize_input(self, message: str) -> str:
        """
        Sanitize user input by removing control characters.
        
        Args:
            message: Raw user input
            
        Returns:
            Sanitized message with control characters removed
        """
        # Remove null bytes and other dangerous control characters
        # Keep tabs (\t), newlines (\n, \r) as they are valid whitespace
        sanitized = ''.join(char for char in message if char >= ' ' or char in '\t\n\r')
        return sanitized

    async def process(
        self,
        session_id: str,
        message: str,
        domain: str = "general"
    ) -> Dict[str, Any]:
        """
        Preprocess a user message.
        
        Args:
            session_id: Unique session identifier
            message: Raw user message
            domain: Detected conversation domain
            
        Returns:
            Dictionary with conditioned input and metadata including timing
        """
        start_time = time.perf_counter()
        
        # Sanitize input to remove control characters
        message = self._sanitize_input(message)

        # Segment the message
        seg_start = time.perf_counter()
        segments = self._segment_message(message)
        segmentation_time_ms = (time.perf_counter() - seg_start) * 1000
        
        # Calculate ambiguity score
        amb_start = time.perf_counter()
        ambiguity_score, ambiguity_flags = self._calculate_ambiguity(message, segments)
        ambiguity_calculation_time_ms = (time.perf_counter() - amb_start) * 1000
        
        # Get relevant anchors for constraint injection
        anchor_start = time.perf_counter()
        constraints_injected = []
        if self.session_anchoring and ambiguity_score > 0.5:
            anchors = await self.session_anchoring.get_relevant_anchors(
                session_id=session_id,
                query=message,
                top_k=3
            )
            if anchors:
                constraints_injected = [a.text for a in anchors]
        anchor_retrieval_time_ms = (time.perf_counter() - anchor_start) * 1000
        
        # Build conditioned input
        conditioned_input = self._build_conditioned_input(
            original_message=message,
            constraints=constraints_injected,
            ambiguity_score=ambiguity_score
        )
        
        # Calculate total processing time
        total_processing_time_ms = (time.perf_counter() - start_time) * 1000
        
        timing_metrics = PreprocessTimingMetrics(
            segmentation_time_ms=segmentation_time_ms,
            ambiguity_calculation_time_ms=ambiguity_calculation_time_ms,
            anchor_retrieval_time_ms=anchor_retrieval_time_ms,
            total_processing_time_ms=total_processing_time_ms
        )
        
        result = PreprocessResult(
            conditioned_input=conditioned_input,
            segments=segments,
            ambiguity_score=ambiguity_score,
            ambiguity_flags=ambiguity_flags,
            constraints_injected=constraints_injected,
            metadata={
                "segment_count": len(segments),
                "domain": domain,
                "has_constraints": len(constraints_injected) > 0
            },
            processing_time_ms=total_processing_time_ms
        )
        
        return {
            "conditioned_input": result.conditioned_input,
            "metadata": {
                "ambiguity_score": result.ambiguity_score,
                "ambiguity_flags": result.ambiguity_flags,
                "segments": result.segments,
                "constraints_injected": result.constraints_injected,
                "processing_time_ms": round(total_processing_time_ms, 4),
                "timing": timing_metrics.to_dict(),
                **result.metadata
            }
        }
    
    def _segment_message(self, message: str) -> List[str]:
        """
        Segment message into semantic units.
        
        Args:
            message: Input message
            
        Returns:
            List of segments
        """
        # Simple segmentation by sentences
        # In production, this could use more sophisticated NLP
        sentences = re.split(r'(?<=[.!?])\s+', message.strip())
        
        # Filter empty segments
        segments = [s.strip() for s in sentences if s.strip()]
        
        # If message is very long, chunk it
        max_segment_length = 500
        chunked_segments = []
        for segment in segments:
            if len(segment) > max_segment_length:
                # Simple chunking by words
                words = segment.split()
                current_chunk = []
                current_length = 0
                
                for word in words:
                    current_chunk.append(word)
                    current_length += len(word) + 1
                    
                    if current_length >= max_segment_length:
                        chunked_segments.append(" ".join(current_chunk))
                        current_chunk = []
                        current_length = 0
                
                if current_chunk:
                    chunked_segments.append(" ".join(current_chunk))
            else:
                chunked_segments.append(segment)
        
        return chunked_segments
    
    def _calculate_ambiguity(
        self,
        message: str,
        segments: List[str]
    ) -> tuple[float, List[str]]:
        """
        Calculate ambiguity score for a message.
        
        Args:
            message: Input message
            segments: Segmented message
            
        Returns:
            Tuple of (ambiguity_score, ambiguity_flags)
        """
        flags = []
        score = 0.0
        message_lower = message.lower()
        
        # Check for vague references
        vague_count = 0
        for pattern in self._vague_references:
            if re.search(pattern, message_lower):
                vague_count += 1
        if vague_count > 0:
            score += min(0.3, vague_count * 0.1)
            flags.append(f"vague_references:{vague_count}")
        
        # Check for uncertainty markers
        uncertainty_count = 0
        for pattern in self._uncertainty_markers:
            if re.search(pattern, message_lower):
                uncertainty_count += 1
        if uncertainty_count > 0:
            score += min(0.2, uncertainty_count * 0.05)
            flags.append(f"uncertainty_markers:{uncertainty_count}")
        
        # Check for missing context (questions without clear subject)
        missing_context = False
        for pattern in self._missing_context:
            if re.search(pattern, message_lower):
                missing_context = True
                break
        if missing_context and len(message) < 50:
            score += 0.25
            flags.append("missing_context")
        
        # Check for very short messages
        if len(message.strip()) < 10:
            score += 0.2
            flags.append("very_short")
        
        # Check for excessive length (may indicate complexity)
        if len(message) > 2000:
            score += 0.15
            flags.append("very_long")
        
        # Check segment coherence
        if len(segments) > 5:
            score += 0.1
            flags.append("many_segments")
        
        return min(1.0, score), flags
    
    def _build_conditioned_input(
        self,
        original_message: str,
        constraints: List[str],
        ambiguity_score: float
    ) -> str:
        """
        Build conditioned input with constraints.
        
        Args:
            original_message: Original user message
            constraints: List of constraint strings
            ambiguity_score: Calculated ambiguity score
            
        Returns:
            Conditioned input string
        """
        parts = []
        
        # Add constraints if available
        if constraints:
            parts.append("[Context from previous conversation:]")
            for constraint in constraints:
                parts.append(f"- {constraint}")
            parts.append("")
        
        # Add ambiguity warning if high
        if ambiguity_score > self.ambiguity_threshold:
            parts.append("[Note: The following query may be ambiguous. Consider asking for clarification if needed.]")
            parts.append("")
        
        # Add original message
        parts.append(original_message)
        
        return "\n".join(parts)
    
    def extract_operators(self, message: str) -> List[Dict[str, Any]]:
        """
        Extract operator tags from message.
        
        Args:
            message: Input message
            
        Returns:
            List of operator dictionaries
        """
        operators = []
        
        # Code blocks
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', message, re.DOTALL)
        for lang, code in code_blocks:
            operators.append({
                "type": "code_block",
                "language": lang or "text",
                "content": code
            })
        
        # Inline code
        inline_code = re.findall(r'`([^`]+)`', message)
        for code in inline_code:
            operators.append({
                "type": "inline_code",
                "content": code
            })
        
        # URLs
        urls = re.findall(r'https?://\S+', message)
        for url in urls:
            operators.append({
                "type": "url",
                "content": url
            })
        
        return operators
