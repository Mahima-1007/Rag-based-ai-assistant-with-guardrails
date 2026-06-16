"""
decision_engine/engine.py — Confidence-based decision making for RAG responses.

DECISION LOGIC:
  HIGH   (confidence >= 0.70) → Generate full grounded answer
  MEDIUM (0.40 <= confidence < 0.70) → Ask clarifying question OR retry
  LOW    (confidence < 0.40)  → Return polite "insufficient information" message

WHY THIS EXISTS:
  Without a decision layer, RAG systems generate "safe-sounding" but
  irrelevant or hallucinated answers when retrieval fails. This layer
  enforces explicit routing before any LLM call is made.

  This is the key architectural decision that separates production RAG
  from naive chatbots: the LLM is NEVER called with poor context.
"""
from dataclasses import dataclass
from enum import Enum

from config import get_settings
from monitoring.logger import get_logger
from validation.retrieval_validator import ValidationResult

settings = get_settings()
logger = get_logger(__name__)


class DecisionType(str, Enum):
    GENERATE = "generate"
    CLARIFY = "clarify"
    INSUFFICIENT = "insufficient"
    RETRY = "retry"


@dataclass
class EngineDecision:
    decision: DecisionType
    confidence_score: float
    confidence_level: str          # HIGH | MEDIUM | LOW
    reason: str
    clarification_question: str | None = None


# Pre-built clarification and insufficiency messages
CLARIFICATION_TEMPLATES = [
    "Could you provide more details about what you're looking for?",
    "Could you rephrase your question with more specific terms?",
    "Which document or section are you referring to?",
    "Could you clarify what aspect you want me to focus on?",
]

INSUFFICIENT_MESSAGE = (
    "I don't have enough information in the uploaded documents to answer this question. "
    "Please upload relevant documents or rephrase your query."
)


def make_decision(validation: ValidationResult, query: str) -> EngineDecision:
    """
    Map retrieval validation result to a routing decision.

    Args:
        validation: Output from validate_retrieval()
        query: Original user query (used to generate clarification question)

    Returns:
        EngineDecision with routing type and metadata
    """
    score = validation.confidence_score

    # ── LOW CONFIDENCE ──────────────────────────────────────────────────────────
    if score < settings.CONFIDENCE_MEDIUM_THRESHOLD:
        logger.info(
            "Decision: INSUFFICIENT",
            score=round(score, 3),
            reason=validation.reason,
        )

        # If retry is suggested and this isn't already a retry, signal retry
        if validation.should_retry:
            return EngineDecision(
                decision=DecisionType.RETRY,
                confidence_score=score,
                confidence_level="LOW",
                reason=validation.reason,
            )

        return EngineDecision(
            decision=DecisionType.INSUFFICIENT,
            confidence_score=score,
            confidence_level="LOW",
            reason=INSUFFICIENT_MESSAGE,
        )

    # ── MEDIUM CONFIDENCE ───────────────────────────────────────────────────────
    if score < settings.CONFIDENCE_HIGH_THRESHOLD:
        logger.info("Decision: CLARIFY", score=round(score, 3))

        # Build a query-aware clarification question
        clarification = _build_clarification(query, validation)

        if validation.should_ask_clarification:
            return EngineDecision(
                decision=DecisionType.CLARIFY,
                confidence_score=score,
                confidence_level="MEDIUM",
                reason=validation.reason,
                clarification_question=clarification,
            )

        # Medium confidence but no ambiguity → attempt generation with caveat
        return EngineDecision(
            decision=DecisionType.GENERATE,
            confidence_score=score,
            confidence_level="MEDIUM",
            reason="Moderate confidence — answer may be partial.",
        )

    # ── HIGH CONFIDENCE ─────────────────────────────────────────────────────────
    logger.info("Decision: GENERATE", score=round(score, 3))
    return EngineDecision(
        decision=DecisionType.GENERATE,
        confidence_score=score,
        confidence_level="HIGH",
        reason="High confidence — generating grounded answer.",
    )


def _build_clarification(query: str, validation: ValidationResult) -> str:
    """Build a context-aware clarification question."""
    query_lower = query.lower()

    if any(word in query_lower for word in ["explain", "describe", "tell me"]):
        return "Could you specify which aspect or section you want me to explain?"

    if any(word in query_lower for word in ["how", "steps", "process"]):
        return "Could you clarify which process or procedure you are referring to?"

    if validation.chunk_count == 0:
        return "No matching content was found. Could you rephrase or specify the topic more clearly?"

    return CLARIFICATION_TEMPLATES[hash(query) % len(CLARIFICATION_TEMPLATES)]
