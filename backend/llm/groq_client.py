"""
llm/groq_client.py — Async Groq API client with streaming support.

MODEL: mixtral-8x7b-32768
  - Mixture-of-Experts architecture — fast inference, strong reasoning
  - 32K context window — handles large compressed contexts
  - Low temperature (0.1) for factual, deterministic responses

STREAMING:
  Uses Server-Sent Events (SSE) to stream tokens to the frontend.
  Tokens are yielded as they arrive from Groq — perceived latency drops
  from 3-5s (wait for full response) to ~200ms (first token appears).

RETRY LOGIC:
  3 retries with exponential backoff on transient API errors.
"""
import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from groq import AsyncGroq

from config import get_settings
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

_groq_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    """Return singleton async Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _groq_client


async def generate_response(prompt: str) -> str:
    """
    Non-streaming completion from Groq — used for hallucination validator.
    Returns the full response as a string.
    """
    client = get_groq_client()

    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.GROQ_MAX_TOKENS,
                temperature=settings.GROQ_TEMPERATURE,
                stream=False,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Groq API error, retrying", attempt=attempt + 1, wait=wait, error=str(e))
            if attempt < 2:
                await asyncio.sleep(wait)
            else:
                raise

    return ""


async def stream_response(prompt: str) -> AsyncGenerator[str, None]:
    """
    Streaming completion from Groq — yields text tokens as they arrive.

    Usage in FastAPI:
        async for token in stream_response(prompt):
            yield f"data: {token}\\n\\n"

    Args:
        prompt: Fully formatted RAG prompt string

    Yields:
        Individual token strings (deltas from Groq streaming API)
    """
    client = get_groq_client()

    try:
        stream = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=settings.GROQ_TEMPERATURE,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    except Exception as e:
        logger.error("Groq streaming error", error=str(e))
        yield "\n\n[Error: Failed to generate response. Please try again.]"


async def generate_summary(text: str, max_words: int = 150) -> str:
    """
    Generate a concise summary of conversation history for memory compression.
    Used by the memory manager to avoid token explosion on long conversations.
    """
    prompt = (
        f"Summarize the following conversation in {max_words} words or less. "
        f"Preserve key facts, decisions, and context:\n\n{text}\n\nSummary:"
    )
    return await generate_response(prompt)
