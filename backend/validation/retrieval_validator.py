"""
validation/retrieval_validator.py — Validates retrieval quality before LLM generation.

ALGORITHM:
  1. Similarity threshold check   → max score >= 0.35 (configurable)
  2. Chunk sufficiency check      → at least 1 chunk passed reranking
  3. Relevance scoring            → average reranker score
  4. Source diversity check       → chunks from at least 1 document
  5. Ambiguity detection          → short queries with pronouns only

OUTPUT:
  ValidationResult with:
    - is_valid: bool
    - confidence_score: float (0.0 – 1.0)
    - reason: str (human-readable explanation)
    - should_retry: bool
    - should_ask_clarification: bool
"""
from dataclasses import dataclass

from config import get_settings
from validation.ambiguity_detector import detect_ambiguity
from validation.relevance_scorer import compute_relevance_score
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    reason: str
    should_retry: bool = False
    should_ask_clarification: bool = False
    top_score: float = 0.0
    avg_score: float = 0.0
    chunk_count: int = 0


def validate_retrieval(
    query: str,
    chunks: list[dict],
    query_embedding: list[float],
) -> ValidationResult:
    """
    Validate the quality of retrieved chunks before passing to LLM.

    Args:
        query: Original user query
        chunks: Reranked chunk list (after CrossEncoder + threshold pruning)
        query_embedding: Pre-computed query vector

    Returns:
        ValidationResult with full diagnostic information
    """
    chunk_count = len(chunks)

    # ── Check 1: Empty retrieval ────────────────────────────────────────────────
    if chunk_count == 0:
        logger.warning("Retrieval validation failed: no chunks", query=query[:80])
        return ValidationResult(
            is_valid=False,
            confidence_score=0.0,
            reason="No relevant content found in your documents for this query.",
            should_retry=True,
            chunk_count=0,
        )

    # ── Check 2: Reranker scores ────────────────────────────────────────────────
    reranker_scores = [c.get("reranker_score", 0.0) for c in chunks]
    top_score = max(reranker_scores)
    avg_score = sum(reranker_scores) / len(reranker_scores)

    if top_score < settings.SIMILARITY_THRESHOLD:
        logger.warning(
            "Retrieval validation failed: low top score",
            top_score=top_score,
            threshold=settings.SIMILARITY_THRESHOLD,
        )
        return ValidationResult(
            is_valid=False,
            confidence_score=top_score,
            reason=f"Retrieved content has low relevance (score: {top_score:.2f}).",
            should_retry=True,
            top_score=top_score,
            avg_score=avg_score,
            chunk_count=chunk_count,
        )

    # ── Check 3: Semantic relevance scoring ────────────────────────────────────
    relevance_score = compute_relevance_score(query_embedding, chunks)

    # ── Check 4: Ambiguity detection ───────────────────────────────────────────
    is_ambiguous = detect_ambiguity(query)
    if is_ambiguous:
        logger.info("Query ambiguity detected", query=query[:80])
        # Still proceed but flag for clarification request
        return ValidationResult(
            is_valid=True,
            confidence_score=min(relevance_score, 0.55),  # Cap at MEDIUM
            reason="Query appears ambiguous. Clarification may improve results.",
            should_ask_clarification=True,
            top_score=top_score,
            avg_score=avg_score,
            chunk_count=chunk_count,
        )

    # ── Final confidence score ──────────────────────────────────────────────────
    # Weighted: 60% reranker avg, 40% semantic relevance
    final_score = (0.6 * avg_score) + (0.4 * relevance_score)
    # Normalize reranker scores (CrossEncoder outputs raw logits, typically -10 to 10)
    # We use a sigmoid-style normalization for the final score
    normalized = 1 / (1 + pow(2.718, -0.5 * final_score))
    normalized = min(max(normalized, 0.0), 1.0)

    logger.info(
        "Retrieval validation passed",
        confidence=round(normalized, 3),
        top_score=round(top_score, 3),
        avg_score=round(avg_score, 3),
        chunk_count=chunk_count,
    )

    return ValidationResult(
        is_valid=True,
        confidence_score=normalized,
        reason="Retrieval quality is sufficient.",
        top_score=top_score,
        avg_score=avg_score,
        chunk_count=chunk_count,
    )
