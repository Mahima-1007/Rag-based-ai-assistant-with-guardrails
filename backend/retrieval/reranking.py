"""
retrieval/reranking.py — CrossEncoder MiniLM reranker.

WHY RERANKING:
  Bi-encoder embeddings (SentenceTransformer) rank quickly but imprecisely.
  CrossEncoder reads query+chunk together — much higher relevance accuracy.
  We run it only on the top-20 merged chunks (not the full corpus) for speed.

MODEL: cross-encoder/ms-marco-MiniLM-L-6-v2
  - Trained on MS MARCO passage re-ranking
  - Outputs a scalar relevance score per (query, passage) pair
  - Prunes irrelevant chunks below the similarity threshold

THRESHOLD PRUNING:
  Any chunk with reranker score < SIMILARITY_THRESHOLD is discarded,
  ensuring only truly relevant context reaches the LLM.
"""
import asyncio
from functools import lru_cache

from sentence_transformers import CrossEncoder

from config import get_settings
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """Load and cache the CrossEncoder model (loaded once at startup)."""
    logger.info("Loading CrossEncoder reranker", model=RERANKER_MODEL)
    model = CrossEncoder(RERANKER_MODEL, max_length=512)
    logger.info("CrossEncoder loaded")
    return model


def _rerank_sync(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """
    Synchronous reranking — runs CrossEncoder on (query, chunk_text) pairs.
    Called in a thread pool to avoid blocking the async event loop.
    """
    model = get_reranker()
    pairs = [(query, chunk["text"]) for chunk in chunks]
    scores = model.predict(pairs, show_progress_bar=False)

    # Attach scores and sort
    for chunk, score in zip(chunks, scores):
        chunk["reranker_score"] = float(score)

    # Sort descending by reranker score
    ranked = sorted(chunks, key=lambda c: c["reranker_score"], reverse=True)

    # Threshold pruning — discard low-relevance chunks
    kept = [
        c for c in ranked
        if c["reranker_score"] >= settings.SIMILARITY_THRESHOLD
    ]

    # Return top_k of the kept chunks
    result = kept[:top_k]

    logger.info(
        "Reranking complete",
        input_count=len(chunks),
        kept_after_threshold=len(kept),
        returned=len(result),
        top_score=result[0]["reranker_score"] if result else 0.0,
    )
    return result


async def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """
    Async wrapper for CrossEncoder reranking.
    Runs in a thread pool to keep the event loop unblocked.
    """
    if not chunks:
        return []

    k = top_k or settings.RERANKER_TOP_K
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _rerank_sync, query, chunks, k)
