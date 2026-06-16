"""
retrieval/bm25_search.py — BM25 keyword retrieval.

WHY BM25:
  Semantic search misses exact keyword matches (model names, IDs, acronyms).
  BM25 complements semantic search by handling precise term matching.
  Together they form hybrid retrieval (best of both worlds).

APPROACH:
  - BM25 index is built lazily from the user's Qdrant chunks
  - Index is cached in Redis (TTL: 30 minutes) to avoid rebuilding per query
  - On cache miss, all chunks are fetched from Qdrant and index is rebuilt
"""
import asyncio
import re
from typing import Any

from rank_bm25 import BM25Okapi

from cache.redis_client import cache_bm25_index, get_cached_bm25_index
from monitoring.logger import get_logger

logger = get_logger(__name__)


def tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    text = text.lower()
    tokens = re.findall(r"\b\w+\b", text)
    return tokens


async def build_bm25_index(user_id: str, corpus: list[dict]) -> BM25Okapi:
    """
    Build BM25 index from a corpus of chunk dicts.
    Each dict must have a 'text' field.
    """
    tokenized_corpus = [tokenize(chunk["text"]) for chunk in corpus]
    loop = asyncio.get_event_loop()
    index = await loop.run_in_executor(None, BM25Okapi, tokenized_corpus)
    logger.info("BM25 index built", user_id=user_id, corpus_size=len(corpus))
    return index


async def get_or_build_bm25(user_id: str, corpus: list[dict]) -> tuple[BM25Okapi, list[dict]]:
    """
    Return cached BM25 index or build + cache a new one.

    Args:
        user_id: User whose chunks form the corpus
        corpus: List of chunk dicts (from Qdrant scroll or semantic results)

    Returns:
        (BM25Okapi index, corpus list)
    """
    cached = await get_cached_bm25_index(user_id)
    if cached:
        logger.debug("BM25 index from cache", user_id=user_id)
        return cached["index"], cached["corpus"]

    index = await build_bm25_index(user_id, corpus)
    await cache_bm25_index(user_id, index, corpus)
    return index, corpus


async def run_bm25_search(
    query: str,
    user_id: str,
    corpus: list[dict],
    top_k: int = 20,
) -> list[dict]:
    """
    Run BM25 retrieval on the provided corpus.

    Args:
        query: Natural language query
        user_id: User ID (for cache key)
        corpus: List of chunk dicts with 'text' field
        top_k: Number of top BM25 results to return

    Returns:
        List of chunk dicts with 'bm25_score' field added, sorted descending
    """
    if not corpus:
        logger.warning("BM25 search called with empty corpus", user_id=user_id)
        return []

    index, indexed_corpus = await get_or_build_bm25(user_id, corpus)

    query_tokens = tokenize(query)
    scores = index.get_scores(query_tokens)

    # Pair chunks with scores and sort
    scored = sorted(
        [(score, chunk) for score, chunk in zip(scores, indexed_corpus)],
        key=lambda x: x[0],
        reverse=True,
    )

    results = []
    for score, chunk in scored[:top_k]:
        if score > 0:  # Only include chunks with non-zero BM25 match
            results.append({**chunk, "bm25_score": float(score)})

    logger.info(
        "BM25 search complete",
        user_id=user_id,
        results_count=len(results),
        top_score=results[0]["bm25_score"] if results else 0.0,
    )
    return results
