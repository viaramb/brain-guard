"""Session Anchoring component - Track facts and detect contradictions."""

import re
import logging
import numpy as np
from typing import Dict, List, Any, Optional
from collections import defaultdict

from ..utils.embedding_service import EmbeddingService
from ..models import Anchor, Contradiction

logger = logging.getLogger(__name__)


class SessionAnchoring:
    """
    Session Anchoring System

    Responsibilities:
    - Extract anchors from responses
    - Store anchors with confidence scores
    - Check new responses against anchor set
    - Detect contradictions
    """

    # Patterns for anchor extraction
    FACTUAL_PATTERNS = [
        r'([A-Z][a-z]+ (?:is|are|was|were) [^.]+)',  # "X is Y"
        r'([A-Z][a-z]+ (?:has|have|had) [^.]+)',  # "X has Y"
        r'([A-Z][a-z]+ (?:can|cannot|will|will not) [^.]+)',  # "X can Y"
    ]

    PROCEDURAL_PATTERNS = [
        r'(?:first|then|next|after that|finally)[,;\s]+([^,;]+)',
        r'step \d+[:\s]+([^,;]+)',
        r'to (?:do|make|create|set up)[^,]+[,;]+([^,;]+)',
    ]

    TEMPORAL_PATTERNS = [
        r'(?:at|on) (\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\s+on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))?)',
        r'(?:at|on) (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
        r'(?:on) (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
        r'(?:in|on) (January|February|March|April|May|June|July|August|September|October|November|December)[^,]*',
        r'(?:by|before|after) (tomorrow|today|yesterday|next week|last week)',
    ]

    CONTEXTUAL_PATTERNS = [
        r'(?:I|we) (?:prefer|like|want|need|require) ([^.]+)',
        r'(?:my|our) ([a-z]+ (?:is|are) [^.]+)',
    ]

    # Greeting/social pleasantries to exclude from anchor extraction
    GREETING_PATTERNS = [
        r'\bhow are you\b',
        r'\bhow do you do\b',
        r'\bnice to meet you\b',
        r'\bgood morning\b',
        r'\bgood afternoon\b',
        r'\bgood evening\b',
        r'\bwhat\'s up\b',
        r'\bsup\b',
        r'\bhey there\b',
        r'\bhello there\b',
        r'\bhi there\b',
    ]

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        max_anchors: int = 50,
        contradiction_check: bool = True,
        contradiction_threshold: float = 0.85
    ):
        self.embedding_service = embedding_service
        self.max_anchors = max_anchors
        self.contradiction_check = contradiction_check
        self.contradiction_threshold = contradiction_threshold

        # Session storage
        self._anchors: Dict[str, List[Anchor]] = defaultdict(list)
        self._anchor_counter: Dict[str, int] = defaultdict(int)

    def _is_greeting_or_social(self, text: str) -> bool:
        """Check if text is a greeting or social pleasantry."""
        text_lower = text.lower()
        for pattern in self.GREETING_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    async def extract_anchors(
        self,
        session_id: str,
        text: str
    ) -> List[Anchor]:
        """
        Extract anchors from text.

        Args:
            session_id: Session identifier
            text: Text to extract anchors from

        Returns:
            List of extracted anchors
        """
        anchors = []

        # Skip anchor extraction for greetings/social pleasantries
        if self._is_greeting_or_social(text):
            return anchors

        # Extract factual anchors
        factual = self._extract_by_pattern(text, self.FACTUAL_PATTERNS, "factual")

        # Extract procedural anchors
        procedural = self._extract_by_pattern(text, self.PROCEDURAL_PATTERNS, "procedural")

        # Extract temporal anchors
        temporal = self._extract_by_pattern(text, self.TEMPORAL_PATTERNS, "temporal")

        # Extract contextual anchors
        contextual = self._extract_by_pattern(text, self.CONTEXTUAL_PATTERNS, "contextual")

        all_extracted = factual + procedural + temporal + contextual

        # Create anchor objects
        import time
        for extracted_text, anchor_type in all_extracted:
            # Skip very short or very long anchors
            if len(extracted_text) < 10 or len(extracted_text) > 500:
                continue

            # Calculate confidence based on pattern match quality
            confidence = self._calculate_confidence(extracted_text, anchor_type)

            # Generate unique ID
            self._anchor_counter[session_id] += 1
            anchor_id = f"{session_id}_anchor_{self._anchor_counter[session_id]}"

            anchor = Anchor(
                id=anchor_id,
                session_id=session_id,
                text=extracted_text,
                anchor_type=anchor_type,
                confidence=confidence,
                timestamp=time.time()
            )

            # Get embedding if service available
            if self.embedding_service:
                try:
                    anchor.embedding, _ = await self.embedding_service.embed(extracted_text)
                except Exception as e:
                    logger.warning(f"Failed to get embedding for anchor: {e}")

            anchors.append(anchor)
            self._anchors[session_id].append(anchor)

        # Enforce max anchors limit
        self._enforce_anchor_limit(session_id)

        return anchors

    def _extract_by_pattern(
        self,
        text: str,
        patterns: List[str],
        anchor_type: str
    ) -> List[tuple]:
        """Extract text matching patterns."""
        results = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                extracted = match.group(1).strip()
                if extracted:
                    results.append((extracted, anchor_type))
        return results

    def _calculate_confidence(self, text: str, anchor_type: str) -> float:
        """Calculate confidence score for an anchor."""
        base_confidence = 0.7

        # Adjust based on anchor type
        type_multipliers = {
            "factual": 1.0,
            "procedural": 0.9,
            "temporal": 0.8,
            "contextual": 0.7
        }

        confidence = base_confidence * type_multipliers.get(anchor_type, 0.7)

        # Adjust based on text characteristics
        if text[0].isupper():  # Starts with capital
            confidence += 0.05
        if text.endswith('.'):  # Complete sentence
            confidence += 0.05
        if len(text) > 50:  # Substantial content
            confidence += 0.05

        return min(1.0, confidence)

    def _enforce_anchor_limit(self, session_id: str) -> None:
        """Enforce maximum anchors per session."""
        anchors = self._anchors[session_id]

        if len(anchors) > self.max_anchors:
            # Sort by (reference_count, timestamp) and remove oldest/least referenced
            anchors.sort(key=lambda a: (a.reference_count, a.timestamp))
            to_remove = len(anchors) - self.max_anchors

            for anchor in anchors[:to_remove]:
                anchor.is_active = False

            self._anchors[session_id] = anchors[to_remove:]

    async def check_contradictions(
        self,
        session_id: str,
        new_text: str
    ) -> List[Contradiction]:
        """
        Check new text against existing anchors for contradictions.

        Args:
            session_id: Session identifier
            new_text: New text to check

        Returns:
            List of detected contradictions
        """
        if not self.contradiction_check:
            return []

        anchors = self._anchors.get(session_id, [])
        if not anchors:
            return []

        contradictions = []

        # Get embedding for new text if service available
        new_embedding = None
        if self.embedding_service:
            try:
                new_embedding, _ = await self.embedding_service.embed(new_text)
            except Exception as e:
                logger.warning(f"Failed to get embedding for contradiction check: {e}")

        for anchor in anchors:
            if not anchor.is_active:
                continue

            # Check for semantic similarity
            similarity = 0.0

            if anchor.embedding is not None and new_embedding is not None:
                similarity = self.embedding_service.cosine_similarity(
                    anchor.embedding,
                    new_embedding
                )
            else:
                # Fallback to simple string similarity
                similarity = self._string_similarity(anchor.text, new_text)

            # High similarity but not exact match might indicate contradiction
            # This is a simplified check - in production, use NLI model
            if 0.5 < similarity < self.contradiction_threshold:
                # Check for negation patterns
                if self._has_contradiction_indicators(anchor.text, new_text):
                    confidence = similarity * 0.8  # Scale confidence

                    contradictions.append(Contradiction(
                        anchor_id=anchor.id,
                        anchor_text=anchor.text,
                        new_text=new_text,
                        similarity=similarity,
                        confidence=confidence
                    ))

        return contradictions

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate simple string similarity."""
        # Jaccard similarity on word sets
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _has_contradiction_indicators(self, text1: str, text2: str) -> bool:
        """Check for linguistic indicators of contradiction."""
        # Negation words
        negations = ['not', "n't", 'never', 'no', 'none', 'nothing', 'nobody']

        text1_lower = text1.lower()
        text2_lower = text2.lower()

        # Check if one has negation and other doesn't
        text1_has_neg = any(neg in text1_lower for neg in negations)
        text2_has_neg = any(neg in text2_lower for neg in negations)

        if text1_has_neg != text2_has_neg:
            return True

        # Check for antonyms (simplified)
        antonym_pairs = [
            ('is', 'is not'), ('was', 'was not'), ('are', 'are not'),
            ('can', 'cannot'), ('will', 'will not'),
            ('all', 'none'), ('always', 'never'),
            ('increase', 'decrease'), ('up', 'down'),
            ('before', 'after'), ('start', 'end')
        ]

        for word1, word2 in antonym_pairs:
            if (word1 in text1_lower and word2 in text2_lower) or \
               (word2 in text1_lower and word1 in text2_lower):
                return True

        return False

    async def get_relevant_anchors(
        self,
        session_id: str,
        query: str,
        top_k: int = 3
    ) -> List[Anchor]:
        """
        Get most relevant anchors for a query.

        Args:
            session_id: Session identifier
            query: Query text
            top_k: Number of anchors to return

        Returns:
            List of relevant anchors
        """
        anchors = self._anchors.get(session_id, [])
        if not anchors or not self.embedding_service:
            return []

        try:
            query_embedding, _ = await self.embedding_service.embed(query)
        except Exception as e:
            logger.warning(f"Failed to get embedding for query: {e}")
            return []

        # Calculate similarities
        scored_anchors = []
        for anchor in anchors:
            if anchor.embedding is not None:
                similarity = self.embedding_service.cosine_similarity(
                    anchor.embedding,
                    query_embedding
                )
                scored_anchors.append((similarity, anchor))

        # Sort by similarity and return top_k
        scored_anchors.sort(key=lambda x: x[0], reverse=True)

        # Update reference counts
        for _, anchor in scored_anchors[:top_k]:
            anchor.reference_count += 1

        return [anchor for _, anchor in scored_anchors[:top_k]]

    def get_anchors(
        self,
        session_id: str,
        anchor_type: Optional[str] = None
    ) -> List[Anchor]:
        """
        Get all anchors for a session.

        Args:
            session_id: Session identifier
            anchor_type: Optional filter by type

        Returns:
            List of anchors
        """
        anchors = self._anchors.get(session_id, [])

        if anchor_type:
            anchors = [a for a in anchors if a.anchor_type == anchor_type]

        return anchors

    def clear_session(self, session_id: str) -> None:
        """Clear all anchors for a session."""
        if session_id in self._anchors:
            del self._anchors[session_id]
        if session_id in self._anchor_counter:
            del self._anchor_counter[session_id]
    def clear_session(self, session_id: str) -> None:
        """Clear all anchors for a session."""
        if session_id in self._anchors:
            del self._anchors[session_id]
        if session_id in self._anchor_counter:
            del self._anchor_counter[session_id]
