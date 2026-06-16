"""
chat/schemas.py — Pydantic schemas for chat API request/response.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)


class ChatMessageRequest(BaseModel):
    session_id: UUID
    query: str = Field(..., min_length=1, max_length=2000)
    document_ids: list[str] | None = Field(default=None, description="Restrict search to specific document IDs")


# ── Response Schemas ─────────────────────────────────────────────────────────────

class ChatSessionResponse(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]
    total: int


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    confidence_level: str | None
    retrieval_score: float | None
    source_documents: dict | None
    latency_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    session_id: UUID
    messages: list[MessageResponse]
    total: int


class StreamStartResponse(BaseModel):
    """Metadata sent as first SSE event before streaming begins."""
    session_id: UUID
    message_id: UUID
    confidence_level: str
    confidence_score: float
    sources: list[dict]
    decision: str


class DeleteSessionResponse(BaseModel):
    message: str
    session_id: UUID
