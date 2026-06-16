"""
validation/relevance_scorer.py — Semantic relevance scoring between query and chunks.

Computes cosine similarity between query embedding and each chunk's text embedding,
returning a normalized average relevance score in [0, 1].
"""
import numpy as np

from documents.embedding import compute_cosine_similarity, embed_texts
from monitoring.logger import get_logger

logger = get_logger(__name__)


def compute_relevance_score(
    query_embedding: list[float],
    chunks: list[dict],
) -> float:
    """
    Compute mean cosine similarity between query and all chunk texts.

    Args:
        query_embedding: Pre-computed query embedding vector
        chunks: List of chunk dicts with 'text' field

    Returns:
        Float in [0, 1] — average relevance score
    """
    if not chunks:
        return 0.0

    chunk_texts = [c.get("text", "") for c in chunks]
    chunk_embeddings = embed_texts(chunk_texts)

    similarities = [
        compute_cosine_similarity(query_embedding, chunk_emb)
        for chunk_emb in chunk_embeddings
    ]

    avg = float(np.mean(similarities))
    logger.debug("Relevance scores computed", avg=round(avg, 4), n=len(similarities))
    return max(0.0, min(1.0, avg))
