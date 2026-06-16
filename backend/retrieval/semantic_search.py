"""
retrieval/semantic_search.py — Qdrant-based semantic vector search.

This module is responsible for:
  - Embedding the user query (with Redis embedding cache)
  - Executing cosine similarity search in the user's Qdrant collection
  - Applying metadata filters (document scope, user ownership)
  - Returning ranked candidate chunks with semantic scores
"""
from cache.redis_client import cache_embedding, get_cached_embedding
from documents.embedding import embed_single_async
from monitoring.logger import get_logger
from vector_db.qdrant_client import semantic_search

logger = get_logger(__name__)


async def run_semantic_search(
    query: str,
    user_id: str,
    top_k: int = 20,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """
    Embed the query (cache-first) and run Qdrant vector search.

    Args:
        query: User's natural language query
        user_id: Authenticated user ID (scopes to their collection)
        top_k: Number of results to return from Qdrant
        document_ids: Optional list to restrict search to specific documents

    Returns:
        List of chunk dicts with 'semantic_score' field added
    """
    # Check embedding cache
    query_embedding = await get_cached_embedding(query)
    if query_embedding is None:
        query_embedding = await embed_single_async(query)
        await cache_embedding(query, query_embedding)
        logger.debug("Query embedded (cache miss)", query_len=len(query))
    else:
        logger.debug("Query embedding from cache")

    results = await semantic_search(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=top_k,
        document_ids=document_ids,
    )

    logger.info(
        "Semantic search complete",
        user_id=user_id,
        results_count=len(results),
        top_score=results[0]["semantic_score"] if results else 0.0,
    )
    return results
