"""Mock embedding service for testing."""

import hashlib
import numpy as np
from typing import List, Dict, Optional, Any


class MockEmbeddingService:
    """
    Mock embedding service for testing.
    
    Generates deterministic embeddings based on text hash.
    """
    
    def __init__(
        self,
        dimensions: int = 1536,
        seed: int = 42,
        cache_enabled: bool = False,
        cache_size: int = 1000
    ):
        self.dimensions = dimensions
        self.seed = seed
        self._rng = np.random.RandomState(seed)
        self._text_vectors: Dict[str, np.ndarray] = {}
        self._cache_enabled = cache_enabled
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def embed(self, text: str) -> np.ndarray:
        """Get embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]
    
    async def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate deterministic mock embeddings."""
        embeddings = []
        
        for text in texts:
            if self._cache_enabled and text in self._text_vectors:
                self._cache_hits += 1
                embeddings.append(self._text_vectors[text])
                continue
            
            self._cache_misses += 1
            
            # Generate deterministic vector based on text using SHA-256
            text_hash = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)
            rng = np.random.RandomState(self.seed + text_hash)
            vector = rng.randn(self.dimensions).astype(np.float32)
            # Normalize
            vector = vector / np.linalg.norm(vector)
            
            if self._cache_enabled:
                self._text_vectors[text] = vector
            
            embeddings.append(vector)
        
        return embeddings
    
    def cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate cosine similarity."""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(v1, v2) / (norm1 * norm2))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0
        
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._text_vectors),
            "hit_rate": hit_rate
        }
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self._text_vectors.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def reset(self) -> None:
        """Reset the mock service."""
        self.clear_cache()
        self._rng = np.random.RandomState(self.seed)
