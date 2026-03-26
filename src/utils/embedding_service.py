"""Embedding service with caching and fallback support."""

import hashlib
import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class CachedEmbedding:
    """Cached embedding with metadata."""
    vector: np.ndarray
    timestamp: float
    access_count: int = 0


@dataclass
class EmbeddingTimingMetrics:
    """Timing metrics for embedding operations."""
    embedding_time_ms: float = 0.0
    cache_hit: bool = False
    batch_size: int = 1
    timestamp: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "embedding_time_ms": round(self.embedding_time_ms, 4),
            "cache_hit": self.cache_hit,
            "batch_size": self.batch_size,
            "timestamp": self.timestamp
        }


class EmbeddingService(ABC):
    """Abstract base class for embedding services."""
    
    def __init__(
        self,
        dimensions: int = 1536,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 3600
    ):
        self.dimensions = dimensions
        self.cache_enabled = cache_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, CachedEmbedding] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    @abstractmethod
    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Get embeddings from the underlying service."""
        pass
    
    async def embed(self, text: str) -> Tuple[np.ndarray, EmbeddingTimingMetrics]:
        """
        Get embedding for a single text with timing metrics.
        
        Args:
            text: Text to embed
            
        Returns:
            Tuple of (embedding vector as numpy array, timing metrics)
        """
        results, timing = await self.embed_batch([text])
        return results[0], timing
    
    async def embed_batch(self, texts: List[str]) -> Tuple[List[np.ndarray], EmbeddingTimingMetrics]:
        """
        Get embeddings for multiple texts with caching and timing metrics.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            Tuple of (list of embedding vectors, timing metrics)
        """
        start_time = time.perf_counter()
        cache_hit = True  # Assume cache hit until proven otherwise
        
        if not texts:
            timing = EmbeddingTimingMetrics(
                embedding_time_ms=0.0,
                cache_hit=True,
                batch_size=0
            )
            return [], timing
        
        results: List[Optional[np.ndarray]] = [None] * len(texts)
        texts_to_embed: List[str] = []
        indices: List[int] = []
        
        # Check cache
        if self.cache_enabled:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                cached = self._cache.get(cache_key)
                
                if cached and (time.time() - cached.timestamp) < self.cache_ttl_seconds:
                    results[i] = cached.vector
                    cached.access_count += 1
                    self._cache_hits += 1
                else:
                    texts_to_embed.append(text)
                    indices.append(i)
                    self._cache_misses += 1
                    cache_hit = False
        else:
            texts_to_embed = texts
            indices = list(range(len(texts)))
            self._cache_misses += len(texts)
            cache_hit = False
        
        # Get embeddings for uncached texts
        if texts_to_embed:
            try:
                embeddings = await self._get_embeddings(texts_to_embed)
                
                # Store in cache and results
                for idx, text, embedding in zip(indices, texts_to_embed, embeddings):
                    results[idx] = embedding
                    
                    if self.cache_enabled:
                        cache_key = self._get_cache_key(text)
                        self._cache[cache_key] = CachedEmbedding(
                            vector=embedding,
                            timestamp=time.time()
                        )
            except Exception as e:
                logger.error(f"Embedding service error: {e}")
                raise
        
        # Calculate timing
        embedding_time_ms = (time.perf_counter() - start_time) * 1000
        timing = EmbeddingTimingMetrics(
            embedding_time_ms=embedding_time_ms,
            cache_hit=cache_hit and len(texts_to_embed) == 0,
            batch_size=len(texts)
        )
        
        return [r for r in results if r is not None], timing
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text using SHA-256."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
            "size": len(self._cache)
        }
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
    
    def cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            v1: First vector
            v2: Second vector
            
        Returns:
            Cosine similarity in range [-1, 1]
        """
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(v1, v2) / (norm1 * norm2))


class MockEmbeddingService(EmbeddingService):
    """
    Mock embedding service for testing.
    
    Generates deterministic embeddings based on text hash.
    """
    
    def __init__(
        self,
        dimensions: int = 1536,
        seed: int = 42,
        cache_enabled: bool = False,
        **kwargs
    ):
        super().__init__(dimensions=dimensions, cache_enabled=cache_enabled, **kwargs)
        self.seed = seed
        self._rng = np.random.RandomState(seed)
        self._text_vectors: Dict[str, np.ndarray] = {}
    
    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate deterministic mock embeddings."""
        embeddings = []
        
        for text in texts:
            if text not in self._text_vectors:
                # Generate deterministic vector based on text
                text_hash = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)
                rng = np.random.RandomState(self.seed + text_hash)
                vector = rng.randn(self.dimensions).astype(np.float32)
                # Normalize
                vector = vector / np.linalg.norm(vector)
                self._text_vectors[text] = vector
            
            embeddings.append(self._text_vectors[text])
        
        return embeddings
    
    def reset(self) -> None:
        """Reset the mock service."""
        self._text_vectors.clear()
        self._rng = np.random.RandomState(self.seed)


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embedding service."""
    
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.model = model
        self.api_key = api_key
        self._client = None
    
    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Get embeddings from OpenAI API."""
        try:
            import openai
            
            if self._client is None:
                self._client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            embeddings = []
            for item in response.data:
                vector = np.array(item.embedding, dtype=np.float32)
                embeddings.append(vector)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise


class LocalEmbeddingService(EmbeddingService):
    """Local sentence-transformers embedding service."""
    
    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        preload_at_startup: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.model_name = model
        self._model = None
        self._loading = False
        self._load_error = None
        self._preload_at_startup = preload_at_startup
        
        if preload_at_startup:
            # Start preloading in background
            import asyncio
            asyncio.create_task(self._load_model_async())
    
    async def _load_model_async(self):
        """Async model loading using thread pool."""
        if self._model is not None or self._loading:
            return

        self._loading = True
        self._load_error = None

        try:
            import asyncio
            from sentence_transformers import SentenceTransformer

            # Use asyncio.to_thread for non-blocking model loading (Python 3.9+)
            self._model = await asyncio.to_thread(
                SentenceTransformer, self.model_name
            )
            logger.info(f"Loaded local embedding model: {self.model_name}")
        except ImportError as e:
            self._load_error = ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise self._load_error
        except Exception as e:
            self._load_error = e
            logger.error(f"Failed to load embedding model: {e}")
            raise
        finally:
            self._loading = False
    
    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self._model is not None and not self._loading
    
    async def wait_for_ready(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for model to finish loading.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if model is ready, False if timeout
            
        Raises:
            Exception: If loading failed
        """
        import asyncio
        
        if self._load_error:
            raise self._load_error
        
        if self.is_ready():
            return True
        
        if not self._loading and self._model is None:
            # Not started loading yet, start now
            await self._load_model_async()
        
        start_time = asyncio.get_event_loop().time()
        while self._loading:
            await asyncio.sleep(0.1)
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                return False
            if self._load_error:
                raise self._load_error
        
        return self.is_ready()
    
    async def _get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Get embeddings from local model."""
        # Ensure model is loaded
        if not self.is_ready():
            await self.wait_for_ready()
        
        if self._model is None:
            raise RuntimeError("Model failed to load")
        
        # Run encoding in thread pool to avoid blocking
        import asyncio

        embeddings = await asyncio.to_thread(
            self._model.encode, texts, convert_to_numpy=True
        )

        return [np.array(e, dtype=np.float32) for e in embeddings]


def create_embedding_service(
    provider: str = "local",
    **kwargs
) -> EmbeddingService:
    """
    Factory function to create embedding service.
    
    Args:
        provider: One of "openai", "local", "mock"
        **kwargs: Additional arguments for the service
        
    Returns:
        EmbeddingService instance
    """
    if provider == "openai":
        return OpenAIEmbeddingService(**kwargs)
    elif provider == "local":
        return LocalEmbeddingService(**kwargs)
    elif provider == "mock":
        return MockEmbeddingService(**kwargs)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
