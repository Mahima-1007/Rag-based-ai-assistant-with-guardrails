"""
documents/embedding.py — SentenceTransformer embedding generation.

Uses all-MiniLM-L6-v2 (384-dim) for fast, high-quality semantic embeddings.
Singleton pattern ensures the model is loaded only once at startup.
"""
import asyncio
from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from config import get_settings
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the SentenceTransformer model (loaded once at startup)."""
    logger.info("Loading embedding model", model=settings.EMBEDDING_MODEL)
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    logger.info("Embedding model loaded", model=settings.EMBEDDING_MODEL)
    return model


def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """
    Generate embeddings for a list of text strings.
    Returns a list of 384-dimensional float vectors.
    """
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,   # L2-normalize for cosine similarity
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def embed_single(text: str) -> List[float]:
    """Generate embedding for a single text string."""
    return embed_texts([text])[0]


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two normalized embedding vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def embed_texts_async(texts: List[str]) -> List[List[float]]:
    """Async wrapper to run embedding in a thread pool (non-blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_texts, texts)


async def embed_single_async(text: str) -> List[float]:
    """Async wrapper for single text embedding."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_single, text)
