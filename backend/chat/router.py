"""
chat/router.py — FastAPI chat routes with SSE streaming support.

Routes:
  POST   /chat/sessions               — Create new session
  GET    /chat/sessions               — List user's sessions
  DELETE /chat/sessions/{id}          — Delete session
  GET    /chat/history/{session_id}   — Get message history
  POST   /chat/message                — Send message (SSE streaming response)
"""
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User
from chat.models import ChatMessage
from chat.schemas import (
    ChatHistoryResponse,
    ChatMessageRequest,
    ChatSessionListResponse,
    ChatSessionResponse,
    CreateSessionRequest,
    DeleteSessionResponse,
    MessageResponse,
)
from chat.service import (
    create_session,
    delete_session,
    get_session_history,
    list_sessions,
    save_message,
)
from database import get_db
from dependencies import get_current_user
from monitoring.logger import get_logger
from orchestration.rag_orchestrator import run_rag_pipeline

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = get_logger(__name__)


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_chat_session(
    payload: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session for the authenticated user."""
    session = await create_session(db, str(current_user.id), payload)
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = await list_sessions(db, str(current_user.id))
    return ChatSessionListResponse(
        sessions=[ChatSessionResponse.model_validate(s) for s in sessions],
        total=len(sessions),
    )


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_chat_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await delete_session(db, str(session_id), str(current_user.id))
    return DeleteSessionResponse(
        message="Session deleted successfully", session_id=session_id
    )


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_history(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = await get_session_history(db, str(session_id), str(current_user.id))
    return ChatHistoryResponse(
        session_id=session_id,
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=len(messages),
    )


@router.post("/message")
async def chat_message(
    payload: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message and receive a streaming SSE response.

    Response format: text/event-stream
    Each event: data: {"type": "...", ...}

    Event types:
      - metadata: pipeline info (confidence, sources, decision)
      - token:    individual LLM token
      - done:     stream complete
      - error:    pipeline error
      - regenerated: hallucination-triggered regenerated answer
    """
    start_time = time.monotonic()

    # Save user message
    await save_message(
        db=db,
        session_id=str(payload.session_id),
        user_id=str(current_user.id),
        role="user",
        content=payload.query,
    )
    await db.commit()

    # Collect full response for saving to DB
    collected_tokens = []
    metadata_event = {}
    done_event = {}

    async def event_generator():
        nonlocal metadata_event, done_event
        full_answer = []
        confidence_level = "LOW"
        confidence_score = 0.0
        sources = []
        guardrail_triggered = False

        try:
            async for sse_str in run_rag_pipeline(
                query=payload.query,
                user_id=str(current_user.id),
                session_id=str(payload.session_id),
                db=db,
                document_ids=payload.document_ids,
            ):
                yield sse_str

                # Parse events to extract metadata for DB storage
                if sse_str.startswith("data: "):
                    try:
                        event_data = json.loads(sse_str[6:])
                        etype = event_data.get("type")

                        if etype == "metadata":
                            confidence_level = event_data.get("confidence_level", "LOW")
                            confidence_score = event_data.get("confidence_score", 0.0)
                            sources = event_data.get("sources", [])

                        elif etype == "token":
                            full_answer.append(event_data.get("text", ""))

                        elif etype == "regenerated":
                            full_answer = [event_data.get("text", "")]

                        elif etype == "error":
                            guardrail_triggered = True

                    except Exception:
                        pass

        finally:
            # Save assistant message to DB after stream completes
            answer_text = "".join(full_answer)
            if answer_text:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                try:
                    async with db as session:
                        await save_message(
                            db=session,
                            session_id=str(payload.session_id),
                            user_id=str(current_user.id),
                            role="assistant",
                            content=answer_text,
                            confidence_level=confidence_level,
                            retrieval_score=confidence_score,
                            source_documents={"sources": sources},
                            guardrail_triggered=guardrail_triggered,
                            latency_ms=latency_ms,
                        )
                        await session.commit()
                except Exception as e:
                    logger.error("Failed to save assistant message", error=str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
