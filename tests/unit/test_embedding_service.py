"""Unit tests for Embedding Service."""

import pytest
import numpy as np
from src.utils.embedding_service import (
    MockEmbeddingService, EmbeddingService, EmbeddingTimingMetrics
)


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    return MockEmbeddingService(dimensions=128, seed=42)


@pytest.mark.unit
class TestMockEmbeddingService:
    """Tests for MockEmbeddingService."""
    
    async def test_embed_single(self, mock_embedding_service):
        """Test embedding a single text."""
        embedding, timing = await mock_embedding_service.embed("Hello world")
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (128,)
        assert embedding.dtype == np.float32
        assert isinstance(timing, EmbeddingTimingMetrics)
        assert timing.batch_size == 1
    
    async def test_embed_batch(self, mock_embedding_service):
        """Test embedding multiple texts."""
        texts = ["Hello", "World", "Test"]
        embeddings, timing = await mock_embedding_service.embed_batch(texts)
        
        assert len(embeddings) == 3
        for emb in embeddings:
            assert emb.shape == (128,)
        assert isinstance(timing, EmbeddingTimingMetrics)
        assert timing.batch_size == 3
    
    async def test_deterministic_embeddings(self, mock_embedding_service):
        """Test that same text produces same embedding."""
        emb1, _ = await mock_embedding_service.embed("Test text")
        emb2, _ = await mock_embedding_service.embed("Test text")
        
        assert np.allclose(emb1, emb2)
    
    async def test_different_texts_different_embeddings(self, mock_embedding_service):
        """Test that different texts produce different embeddings."""
        emb1, _ = await mock_embedding_service.embed("Hello")
        emb2, _ = await mock_embedding_service.embed("Goodbye")
        
        assert not np.allclose(emb1, emb2)
    
    async def test_normalized_embeddings(self, mock_embedding_service):
        """Test that embeddings are normalized."""
        embedding, _ = await mock_embedding_service.embed("Test")
        norm = np.linalg.norm(embedding)
        
        assert np.isclose(norm, 1.0, atol=0.01)
    
    async def test_cosine_similarity_identical(self, mock_embedding_service):
        """Test cosine similarity of identical vectors."""
        emb, _ = await mock_embedding_service.embed("Test")
        similarity = mock_embedding_service.cosine_similarity(emb, emb)
        
        assert np.isclose(similarity, 1.0)
    
    async def test_cosine_similarity_orthogonal(self, mock_embedding_service):
        """Test cosine similarity of different vectors."""
        emb1, _ = await mock_embedding_service.embed("Hello world this is a test")
        emb2, _ = await mock_embedding_service.embed("Completely different topic about space")
        similarity = mock_embedding_service.cosine_similarity(emb1, emb2)
        
        # Should be between -1 and 1
        assert -1.0 <= similarity <= 1.0
    
    def test_reset(self, mock_embedding_service):
        """Test reset clears stored vectors."""
        # This test doesn't need async since reset is sync
        mock_embedding_service.reset()
        
        # After reset, internal state should be cleared
        assert len(mock_embedding_service._text_vectors) == 0
    
    async def test_empty_batch(self, mock_embedding_service):
        """Test embedding empty batch."""
        embeddings, timing = await mock_embedding_service.embed_batch([])
        
        assert embeddings == []
        assert isinstance(timing, EmbeddingTimingMetrics)
        assert timing.batch_size == 0
    
    async def test_different_dimensions(self):
        """Test different embedding dimensions."""
        service = MockEmbeddingService(dimensions=256)
        embedding, _ = await service.embed("Test")
        
        assert embedding.shape == (256,)


@pytest.mark.unit
class TestEmbeddingServiceBase:
    """Tests for base EmbeddingService class."""
    
    async def test_caching(self):
        """Test embedding caching."""
        service = MockEmbeddingService(dimensions=128, cache_enabled=True)
        
        # First call - cache miss
        emb1, timing1 = await service.embed("Test text")
        
        # Second call - should be cached
        emb2, timing2 = await service.embed("Test text")
        
        stats = service.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
    
    def test_cache_stats(self):
        """Test cache statistics."""
        service = MockEmbeddingService(dimensions=128, cache_enabled=True)
        
        stats = service.get_cache_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "size" in stats
    
    def test_clear_cache(self):
        """Test clearing cache."""
        service = MockEmbeddingService(dimensions=128, cache_enabled=True)
        
        service.clear_cache()
        
        stats = service.get_cache_stats()
        assert stats["size"] == 0
    
    def test_cosine_similarity_zero_vectors(self):
        """Test cosine similarity with zero vectors."""
        service = MockEmbeddingService(dimensions=128)
        
        v1 = np.zeros(128)
        v2 = np.array([1.0] * 128)
        
        similarity = service.cosine_similarity(v1, v2)
        
        assert similarity == 0.0
    
    def test_cache_disabled(self):
        """Test with caching disabled."""
        service = MockEmbeddingService(dimensions=128, cache_enabled=False)
        
        stats = service.get_cache_stats()
        assert stats["size"] == 0
