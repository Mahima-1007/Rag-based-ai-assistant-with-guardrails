"""
vector_db/qdrant_client.py — Qdrant vector database client.

Design:
  - One collection per user: user_{user_id}_docs
  - Each point stores child chunk text + parent chunk text in payload
  - Cosine distance for semantic similarity matching
  - Payload metadata enables filtering by document_id, user_id
"""
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from config import get_settings
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Return singleton Qdrant async client."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=30,
        )
    return _client


def collection_name(user_id: str) -> str:
    """Per-user collection name — guarantees hard document isolation."""
    return f"user_{user_id.replace('-', '_')}_docs"


async def ensure_collection(user_id: str) -> str:
    """
    Create Qdrant collection for the user if it does not exist.
    Returns the collection name.
    """
    client = get_qdrant_client()
    coll = collection_name(user_id)

    existing = await client.get_collections()
    existing_names = [c.name for c in existing.collections]

    if coll not in existing_names:
        await client.create_collection(
            collection_name=coll,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        # Create payload indexes for fast filtering
        await client.create_payload_index(
            collection_name=coll,
            field_name="document_id",
            field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
        )
        await client.create_payload_index(
            collection_name=coll,
            field_name="user_id",
            field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
        )
        logger.info("Qdrant collection created", collection=coll)

    return coll


async def upsert_chunks(user_id: str, chunks: list[dict]) -> int:
    """
    Upsert a list of chunk dicts into the user's Qdrant collection.

    Each chunk dict must have:
      - chunk_id, parent_chunk_id, document_id, user_id
      - text (child), parent_text
      - embedding (List[float])
      - chunk_index, source_filename, page_number
    """
    client = get_qdrant_client()
    coll = await ensure_collection(user_id)

    points = [
        PointStruct(
            id=chunk["chunk_id"],
            vector=chunk["embedding"],
            payload={
                "chunk_id": chunk["chunk_id"],
                "parent_chunk_id": chunk["parent_chunk_id"],
                "document_id": chunk["document_id"],
                "user_id": chunk["user_id"],
                "text": chunk["text"],
                "parent_text": chunk["parent_text"],
                "chunk_index": chunk["chunk_index"],
                "source_filename": chunk["source_filename"],
                "page_number": chunk["page_number"],
            },
        )
        for chunk in chunks
    ]

    await client.upsert(collection_name=coll, points=points, wait=True)
    logger.info("Chunks upserted to Qdrant", collection=coll, count=len(points))
    return len(points)


async def semantic_search(
    user_id: str,
    query_embedding: list[float],
    top_k: int = 20,
    document_ids: list[str] | None = None,
) -> list[dict]:
    """
    Perform semantic (vector) search in the user's collection.
    Optionally filter by specific document IDs for scoped retrieval.
    Returns list of payload dicts with similarity scores.
    """
    client = get_qdrant_client()
    coll = collection_name(user_id)

    # Build optional document_id filter
    query_filter = None
    if document_ids:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=doc_id),
                )
                for doc_id in document_ids
            ]
        )

    results = await client.search(
        collection_name=coll,
        query_vector=query_embedding,
        limit=top_k,
        query_filter=query_filter,
        with_payload=True,
        with_vectors=False,
    )

    return [
        {**hit.payload, "semantic_score": hit.score}
        for hit in results
    ]


async def delete_document_vectors(user_id: str, document_id: str) -> None:
    """Delete all vectors associated with a specific document for a user."""
    client = get_qdrant_client()
    coll = collection_name(user_id)

    await client.delete(
        collection_name=coll,
        points_selector=qdrant_models.FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )
    logger.info("Document vectors deleted", document_id=document_id, collection=coll)


async def get_collection_stats(user_id: str) -> dict:
    """Return stats (vector count, etc.) for the user's collection."""
    client = get_qdrant_client()
    coll = collection_name(user_id)
    try:
        info = await client.get_collection(collection_name=coll)
        return {
            "collection": coll,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
        }
    except Exception:
        return {"collection": coll, "vectors_count": 0, "points_count": 0}
