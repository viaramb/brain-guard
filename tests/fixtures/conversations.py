# Test fixtures and utilities

import pytest
import numpy as np


# Sample coherent conversations for testing
COHERENT_CONVERSATIONS = [
    {
        "name": "python_basics",
        "turns": [
            ("What is Python?", "Python is a high-level programming language."),
            ("What can I do with it?", "You can build web apps, scripts, and data pipelines."),
            ("Is it easy to learn?", "Yes, Python has a gentle learning curve and readable syntax."),
        ]
    },
    {
        "name": "cooking_pasta",
        "turns": [
            ("How do I cook pasta?", "Boil water, add salt, then add pasta and cook until al dente."),
            ("How long should I cook it?", "Usually 8-12 minutes depending on the pasta type."),
            ("What sauce goes well?", "Marinara, Alfredo, or pesto are popular choices."),
        ]
    }
]


# Conversations with known drift points
DRIFT_CONVERSATIONS = [
    {
        "name": "gradual_drift",
        "turns": [
            ("Tell me about dogs", "Dogs are loyal pets."),
            ("What about pets in general?", "Pets provide companionship."),
            ("How about animals?", "Animals are living organisms."),
            ("What is biology?", "Biology is the study of life."),
            ("Tell me about science", "Science is a systematic study."),
        ],
        "drift_points": [2, 4]
    }
]


# Conversations with ruptures
RUPTURE_CONVERSATIONS = [
    {
        "name": "sudden_rupture",
        "turns": [
            ("What is Python?", "Python is a programming language."),
            ("How do I install it?", "You can download it from python.org."),
            ("What about the moon?", "The moon is Earth's natural satellite."),
        ],
        "rupture_point": 2
    }
]


# Edge cases for testing
EDGE_CASES = [
    {
        "name": "empty_message",
        "message": "",
        "expected_behavior": "graceful_handling"
    },
    {
        "name": "very_long_message",
        "message": "Word " * 5000,
        "expected_behavior": "truncate_or_chunk"
    },
    {
        "name": "unicode_message",
        "message": "Hello 👋 World 🌍 你好 मन",
        "expected_behavior": "proper_handling"
    },
    {
        "name": "special_characters",
        "message": "```code``` **bold** *italic* `inline`",
        "expected_behavior": "preserve_formatting"
    },
    {
        "name": "single_character",
        "message": "?",
        "expected_behavior": "handle_short"
    }
]


def generate_mock_embedding(text: str, dimensions: int = 128, seed: int = 42) -> np.ndarray:
    """Generate a deterministic mock embedding for text."""
    import hashlib
    
    text_hash = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)
    rng = np.random.RandomState(seed + text_hash)
    vector = rng.randn(dimensions).astype(np.float32)
    return vector / np.linalg.norm(vector)


def calculate_similarity(text1: str, text2: str, dimensions: int = 128) -> float:
    """Calculate mock similarity between two texts."""
    emb1 = generate_mock_embedding(text1, dimensions)
    emb2 = generate_mock_embedding(text2, dimensions)
    
    return float(np.dot(emb1, emb2))
