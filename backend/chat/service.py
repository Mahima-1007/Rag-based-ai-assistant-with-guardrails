"""
chat/service.py — Chat session management: create, list, delete, save messages.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.models import ChatMessage, ChatSession
from chat.schemas import CreateSessionRequest
from monitoring.logger import get_logger

logger = get_logger(__name__)


async def create_session(
    db: AsyncSession, user_id: str, payload: CreateSessionRequest
) -> ChatSession:
    session = ChatSession(
        user_id=uuid.UUID(user_id),
        title=payload.title or "New Chat",
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    logger.info("Chat session created", session_id=str(session.id))
    return session


async def list_sessions(db: AsyncSession, user_id: str) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == uuid.UUID(user_id))
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


async def get_session_history(
    db: AsyncSession, session_id: str, user_id: str
) -> list[ChatMessage]:
    # Verify ownership
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == uuid.UUID(session_id),
            ChatSession.user_id == uuid.UUID(user_id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()


async def delete_session(db: AsyncSession, session_id: str, user_id: str) -> None:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == uuid.UUID(session_id),
            ChatSession.user_id == uuid.UUID(user_id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.flush()
    logger.info("Chat session deleted", session_id=session_id)


async def save_message(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    confidence_level: str | None = None,
    retrieval_score: float | None = None,
    source_documents: dict | None = None,
    guardrail_triggered: bool = False,
    latency_ms: int | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=uuid.UUID(session_id),
        user_id=uuid.UUID(user_id),
        role=role,
        content=content,
        confidence_level=confidence_level,
        retrieval_score=retrieval_score,
        source_documents=source_documents,
        guardrail_triggered=guardrail_triggered,
        latency_ms=latency_ms,
    )
    db.add(msg)

    # Update session updated_at
    await db.execute(
        select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
    )
    await db.flush()
    await db.refresh(msg)
    return msg
