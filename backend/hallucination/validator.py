"""
hallucination/validator.py — Post-generation hallucination validation.

ALGORITHM:
  1. Embed the generated answer
  2. Embed each context chunk (child text)
  3. Compute max cosine similarity between answer and any chunk
  4. If similarity < HALLUCINATION_THRESHOLD → answer is likely hallucinated
  5. If hallucinated → reject and return safe fallback message

WHY THIS EXISTS:
  Even with grounded prompting, the LLM may occasionally:
  - Interpolate facts not present in context
  - Confuse similar-sounding concepts across documents
  - Generate plausible but unsupported claims

  This validation layer catches those cases BEFORE they reach the user.

THRESHOLD:
  0.30 — conservative but effective for MiniLM-L6 embeddings.
  A legitimate grounded answer always has at least moderate semantic overlap
  with the context it was derived from.
"""
from dataclasses import dataclass

from documents.embedding import compute_cosine_similarity, embed_single, embed_texts
from monitoring.logger import get_logger

logger = get_logger(__name__)

HALLUCINATION_THRESHOLD = 0.60   # Min similarity for answer to be considered grounded


@dataclass
class HallucinationResult:
    is_grounded: bool
    max_similarity: float
    avg_similarity: float
    reason: str


def validate_answer_grounding(
    answer: str,
    chunks: list[dict],
) -> HallucinationResult:
    """
    Check if a generated answer is semantically grounded in the retrieved chunks.

    Args:
        answer: The LLM-generated answer string
        chunks: Reranked chunks used as context (must have 'text' field)

    Returns:
        HallucinationResult — if is_grounded=False, the answer should be rejected.
    """
    if not answer or not answer.strip():
        return HallucinationResult(
            is_grounded=False,
            max_similarity=0.0,
            avg_similarity=0.0,
            reason="Empty answer generated.",
        )

    # Check for explicit refusal (always grounded by definition)
    refusal_phrases = [
        "i do not have enough information",
        "i cannot answer",
        "not mentioned in",
        "not provided in",
        "no information available",
    ]
    answer_lower = answer.lower()
    if any(phrase in answer_lower for phrase in refusal_phrases):
        return HallucinationResult(
            is_grounded=True,
            max_similarity=1.0,
            avg_similarity=1.0,
            reason="Answer is an explicit refusal — always grounded.",
        )

    if not chunks:
        return HallucinationResult(
            is_grounded=False,
            max_similarity=0.0,
            avg_similarity=0.0,
            reason="No context chunks available for grounding check.",
        )

    # Embed answer and all chunk texts
    answer_embedding = embed_single(answer)
    chunk_texts = [c.get("text", "") for c in chunks if c.get("text")]

    if not chunk_texts:
        return HallucinationResult(
            is_grounded=False,
            max_similarity=0.0,
            avg_similarity=0.0,
            reason="Chunks have no text content.",
        )

    chunk_embeddings = embed_texts(chunk_texts)

    similarities = [
        compute_cosine_similarity(answer_embedding, chunk_emb)
        for chunk_emb in chunk_embeddings
    ]

    max_sim = max(similarities)
    avg_sim = sum(similarities) / len(similarities)

    is_grounded = max_sim >= HALLUCINATION_THRESHOLD

    logger.info(
        "Hallucination check",
        is_grounded=is_grounded,
        max_similarity=round(max_sim, 4),
        avg_similarity=round(avg_sim, 4),
        threshold=HALLUCINATION_THRESHOLD,
    )

    if not is_grounded:
        logger.warning(
            "Potential hallucination detected",
            max_similarity=round(max_sim, 4),
            threshold=HALLUCINATION_THRESHOLD,
        )

    return HallucinationResult(
        is_grounded=is_grounded,
        max_similarity=round(max_sim, 4),
        avg_similarity=round(avg_sim, 4),
        reason=(
            "Answer is grounded in context."
            if is_grounded
            else f"Answer has low similarity to context (max={max_sim:.3f}). Possible hallucination."
        ),
    )


HALLUCINATION_FALLBACK = (
    "I was unable to generate a reliable answer grounded in your documents. "
    "Please try rephrasing your question or uploading more relevant documents."
)
