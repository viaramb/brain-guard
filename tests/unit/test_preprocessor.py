"""Unit tests for Preprocessor component."""

import pytest
from src.components.preprocessor import Preprocessor
from src.utils.embedding_service import MockEmbeddingService
from src.components.session_anchoring import SessionAnchoring


@pytest.fixture
def embedding_service():
    """Create mock embedding service."""
    return MockEmbeddingService(dimensions=128)


@pytest.fixture
def preprocessor(embedding_service):
    """Create preprocessor instance."""
    return Preprocessor(
        embedding_service=embedding_service,
        ambiguity_threshold=0.70
    )


@pytest.fixture
def preprocessor_with_anchoring(embedding_service):
    """Create preprocessor with session anchoring."""
    anchoring = SessionAnchoring(embedding_service=embedding_service)
    return Preprocessor(
        embedding_service=embedding_service,
        ambiguity_threshold=0.70,
        session_anchoring=anchoring
    )


@pytest.mark.unit
class TestPreprocessor:
    """Tests for Preprocessor (Layer 1)."""
    
    async def test_empty_prompt(self, preprocessor):
        """PRE-001: Empty prompt handling."""
        result = await preprocessor.process(
            session_id="test-session",
            message="",
            domain="general"
        )
        
        assert result["conditioned_input"] == ""
        assert result["metadata"]["ambiguity_score"] == 0.2  # Empty triggers very_short flag
        assert "very_short" in result["metadata"]["ambiguity_flags"]
    
    async def test_simple_prompt(self, preprocessor):
        """PRE-002: Simple prompt with low ambiguity."""
        result = await preprocessor.process(
            session_id="test-session",
            message="What is the weather today?",
            domain="general"
        )
        
        assert result["conditioned_input"] != ""
        assert result["metadata"]["ambiguity_score"] < 0.3
        assert len(result["metadata"]["segments"]) > 0
    
    async def test_ambiguous_prompt(self, preprocessor):
        """PRE-003: Ambiguous prompt detection."""
        result = await preprocessor.process(
            session_id="test-session",
            message="Tell me about it",
            domain="general"
        )

        # "Tell me about it" contains "it" which is a vague reference
        # Score should be at least 0.1 from vague_references (1 match * 0.1)
        assert result["metadata"]["ambiguity_score"] > 0.0
        assert any("vague" in flag for flag in result["metadata"]["ambiguity_flags"])
    
    async def test_multi_sentence_prompt(self, preprocessor):
        """PRE-004: Multi-sentence segmentation."""
        message = "First sentence. Second sentence. Third sentence."
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert len(result["metadata"]["segments"]) >= 3
    
    async def test_unicode_handling(self, preprocessor):
        """PRE-006: Unicode handling."""
        message = "Hello 👋 World 🌍 你好"
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert "👋" in result["conditioned_input"]
        assert "🌍" in result["conditioned_input"]
        assert "你好" in result["conditioned_input"]
    
    async def test_very_long_prompt(self, preprocessor):
        """PRE-007: Very long prompt handling."""
        message = "Word " * 2000  # Very long message
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert "very_long" in result["metadata"]["ambiguity_flags"]
    
    async def test_special_characters(self, preprocessor):
        """PRE-008: Special characters preservation."""
        message = "```python\nprint('hello')\n```\n**bold** and *italic*"
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert "```python" in result["conditioned_input"]
        assert "**bold**" in result["conditioned_input"]
    
    async def test_uncertainty_markers(self, preprocessor):
        """Test detection of uncertainty markers."""
        message = "Maybe we could possibly do something sort of like that."
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert result["metadata"]["ambiguity_score"] > 0
        assert any("uncertainty" in flag for flag in result["metadata"]["ambiguity_flags"])
    
    async def test_vague_references(self, preprocessor):
        """Test detection of vague references."""
        message = "It is there. They said that."
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert result["metadata"]["ambiguity_score"] > 0
        assert any("vague" in flag for flag in result["metadata"]["ambiguity_flags"])
    
    async def test_missing_context(self, preprocessor):
        """Test detection of missing context."""
        message = "What?"
        result = await preprocessor.process(
            session_id="test-session",
            message=message,
            domain="general"
        )
        
        assert result["metadata"]["ambiguity_score"] > 0
    
    async def test_extract_operators(self, preprocessor):
        """Test operator extraction."""
        message = "```python\ncode here\n``` and `inline` and https://example.com"
        operators = preprocessor.extract_operators(message)
        
        assert len(operators) >= 3
        assert any(op["type"] == "code_block" for op in operators)
        assert any(op["type"] == "inline_code" for op in operators)
        assert any(op["type"] == "url" for op in operators)
