"""
llm/memory_manager.py — Short-term and summarized conversation memory.

PROBLEM WITH FULL HISTORY:
  Sending all previous messages to Groq wastes tokens and increases latency.
  A 20-turn conversation can have 10,000+ tokens of history alone.

SOLUTION — Two-tier memory:
  Tier 1 (Recent):   Last 4 messages verbatim (immediate context)
  Tier 2 (Summary):  Older messages summarized into 150 words via Groq

RESULT:
  The LLM always has conversational coherence without token explosion.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from monitoring.logger import get_logger

logger = get_logger(__name__)

RECENT_TURNS = 4          # Number of recent messages to include verbatim
MAX_SUMMARY_CHARS = 1000  # Max characters for the conversation summary


async def get_conversation_memory(
    db: AsyncSession,
    session_id: str,
) -> str:
    """
    Build memory string from chat history using two-tier strategy.

    Args:
        db: Async DB session
        session_id: Chat session UUID

    Returns:
        Formatted memory string for injection into prompt
    """
    import uuid
    from chat.models import ChatMessage

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()

    if not messages:
        return ""

    # Split into older and recent
    recent = messages[-RECENT_TURNS * 2:]        # last N turns (user+assistant pairs)
    older = messages[: -RECENT_TURNS * 2] if len(messages) > RECENT_TURNS * 2 else []

    # Format recent messages verbatim
    recent_text = "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
        for m in recent
    )

    # Summarize older messages if they exist
    summary_text = ""
    if older:
        older_text = "\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
            for m in older
        )
        # Only summarize if older conversation is long enough
        if len(older_text) > 500:
            try:
                from llm.groq_client import generate_summary
                summary_text = await generate_summary(older_text, max_words=150)
                summary_text = f"[Earlier conversation summary]: {summary_text}\n\n"
            except Exception as e:
                logger.warning("Memory summarization failed", error=str(e))
                summary_text = ""  # Graceful fallback

    memory = summary_text + recent_text
    return memory[:MAX_SUMMARY_CHARS]  # Hard cap to prevent token overflow
