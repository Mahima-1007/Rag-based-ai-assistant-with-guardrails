"""
cache/redis_client.py — Redis caching layer for the RAG pipeline.

Cache Types:
  - Query cache      → Full RAG response for identical queries (TTL: 300s)
  - Embedding cache  → Precomputed embeddings by text hash (TTL: 3600s)
  - Retrieval cache  → Retrieved chunks for a query (TTL: 180s)
  - Response cache   → Final LLM response (TTL: 300s)
  - BM25 index cache → Serialized BM25 index per user (TTL: 1800s)

WHY REDIS:
  Identical queries from the same user skip the entire RAG pipeline,
  reducing latency from ~2-5s to <50ms.
"""
import hashlib
import json
import pickle
from typing import Any

import redis.asyncio as aioredis

from config import get_settings
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return singleton async Redis connection."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,   # binary for pickle support
        )
    return _redis


def hash_text(text: str) -> str:
    """SHA-256 hash of a string, used as cache key component."""
    return hashlib.sha256(text.encode()).hexdigest()[:32]


# ─── Embedding Cache ────────────────────────────────────────────────────────────

async def get_cached_embedding(text: str) -> list[float] | None:
    """Return cached embedding or None."""
    redis = await get_redis()
    key = f"emb:{hash_text(text)}"
    data = await redis.get(key)
    if data:
        logger.debug("Embedding cache hit", key=key)
        return json.loads(data)
    return None


async def cache_embedding(text: str, embedding: list[float]) -> None:
    """Cache an embedding vector for a text string."""
    redis = await get_redis()
    key = f"emb:{hash_text(text)}"
    await redis.setex(key, settings.CACHE_TTL_EMBEDDING, json.dumps(embedding))


# ─── Retrieval Cache ────────────────────────────────────────────────────────────

async def get_cached_retrieval(user_id: str, query: str) -> list[dict] | None:
    """Return cached retrieval results or None."""
    redis = await get_redis()
    key = f"ret:{user_id}:{hash_text(query)}"
    data = await redis.get(key)
    if data:
        logger.debug("Retrieval cache hit", user_id=user_id)
        return json.loads(data)
    return None


async def cache_retrieval(user_id: str, query: str, chunks: list[dict]) -> None:
    """Cache retrieved chunks for a user+query combination."""
    redis = await get_redis()
    key = f"ret:{user_id}:{hash_text(query)}"
    await redis.setex(key, settings.CACHE_TTL_RETRIEVAL, json.dumps(chunks))


# ─── Response Cache ─────────────────────────────────────────────────────────────

async def get_cached_response(user_id: str, query: str) -> dict | None:
    """Return cached final response or None."""
    redis = await get_redis()
    key = f"resp:{user_id}:{hash_text(query)}"
    data = await redis.get(key)
    if data:
        logger.debug("Response cache hit", user_id=user_id)
        return json.loads(data)
    return None


async def cache_response(user_id: str, query: str, response: dict) -> None:
    """Cache the final RAG response for a user+query combination."""
    redis = await get_redis()
    key = f"resp:{user_id}:{hash_text(query)}"
    await redis.setex(key, settings.CACHE_TTL_RESPONSE, json.dumps(response))


# ─── BM25 Index Cache ────────────────────────────────────────────────────────────

async def get_cached_bm25_index(user_id: str) -> Any | None:
    """Return deserialized BM25 index for the user or None."""
    redis = await get_redis()
    key = f"bm25:{user_id}"
    data = await redis.get(key)
    if data:
        logger.debug("BM25 cache hit", user_id=user_id)
        return pickle.loads(data)
    return None


async def cache_bm25_index(user_id: str, bm25_index: Any, corpus: list[dict]) -> None:
    """Cache serialized BM25 index for a user (pickle for non-JSON-serializable obj)."""
    redis = await get_redis()
    key = f"bm25:{user_id}"
    payload = pickle.dumps({"index": bm25_index, "corpus": corpus})
    await redis.setex(key, 1800, payload)


async def invalidate_user_cache(user_id: str) -> None:
    """Invalidate all caches for a user (called on new document upload)."""
    redis = await get_redis()
    pattern = f"*:{user_id}:*"
    keys = await redis.keys(pattern)
    bm25_key = f"bm25:{user_id}"
    all_keys = list(keys) + [bm25_key]
    if all_keys:
        await redis.delete(*all_keys)
    logger.info("User cache invalidated", user_id=user_id, keys_deleted=len(all_keys))


async def ping_redis() -> bool:
    """Health check for Redis connection."""
    try:
        redis = await get_redis()
        return await redis.ping()
    except Exception:
        return False
