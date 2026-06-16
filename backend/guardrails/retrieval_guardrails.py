"""
guardrails/retrieval_guardrails.py — Retrieval-level access control and ownership validation.

PROTECTIONS:
  1. Session ownership validation  — user can only access their own chat sessions
  2. Document ownership check      — restrict retrieval to user-owned documents
  3. Cross-user contamination prevention — Qdrant collection is per-user (hard isolation)
  4. Metadata filter enforcement   — every Qdrant query includes user_id in payload filter

WHY THIS EXISTS:
  Even with per-user Qdrant collections, an extra validation layer ensures:
  - No accidental cross-user retrieval if collection names are misconfigured
  - Document IDs supplied by client are actually owned by the requesting user
  - Session tokens are not reused across users
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from documents.models import Document
from monitoring.logger import get_logger

logger = get_logger(__name__)


async def validate_document_ownership(
    db: AsyncSession,
    document_ids: list[str],
    user_id: str,
) -> list[str]:
    """
    Verify that all requested document IDs belong to the authenticated user.

    Args:
        db: Async DB session
        document_ids: List of document UUIDs supplied by client
        user_id: Authenticated user's UUID

    Returns:
        Validated list of document IDs (same as input if all valid)

    Raises:
        HTTPException 403 if any document is not owned by the user
    """
    if not document_ids:
        return []

    result = await db.execute(
        select(Document.id).where(
            Document.id.in_([uuid.UUID(d) for d in document_ids]),
            Document.user_id == uuid.UUID(user_id),
            Document.status == "ready",
        )
    )
    owned_ids = {str(row[0]) for row in result.fetchall()}

    unauthorized = set(document_ids) - owned_ids
    if unauthorized:
        logger.warning(
            "Unauthorized document access attempt",
            user_id=user_id,
            unauthorized_ids=list(unauthorized),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: one or more documents not found or not owned by you.",
        )

    return document_ids


async def get_user_document_ids(db: AsyncSession, user_id: str) -> list[str]:
    """
    Return all ready document IDs for a user.
    Used when no specific documents are requested — search across all user docs.
    """
    result = await db.execute(
        select(Document.id).where(
            Document.user_id == uuid.UUID(user_id),
            Document.status == "ready",
        )
    )
    return [str(row[0]) for row in result.fetchall()]


def validate_chunk_ownership(chunks: list[dict], user_id: str) -> list[dict]:
    """
    Post-retrieval validation: filter out any chunks with mismatched user_id.
    Acts as a safety net against Qdrant misconfiguration.
    """
    safe = [c for c in chunks if c.get("user_id") == user_id]
    dropped = len(chunks) - len(safe)
    if dropped > 0:
        logger.error(
            "Cross-user chunk contamination detected and blocked",
            user_id=user_id,
            dropped_chunks=dropped,
        )
    return safe
