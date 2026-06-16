"""
retrieval/context_compression.py — Context compression before LLM generation.

WHY COMPRESSION:
  Even after reranking, parent chunks can be large (up to 1000 tokens each).
  Sending 5 × 1000-token chunks = 5000 tokens of context → expensive + slow.
  We compress by keeping only the most query-relevant sentences from each chunk.

APPROACH:
  Sentence-level scoring using cosine similarity between:
    - query embedding
    - each sentence embedding from the parent chunk
  Top-N sentences by similarity are kept, preserving document order.
"""
import re

from documents.embedding import compute_cosine_similarity, embed_texts
from monitoring.logger import get_logger

logger = get_logger(__name__)

MAX_CONTEXT_CHARS = 4000   # Hard cap on total compressed context characters
SENTENCES_PER_CHUNK = 5    # Max sentences to keep per parent chunk


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def compress_chunk(query_embedding: list[float], parent_text: str) -> str:
    """
    Compress a parent chunk by keeping only the most query-relevant sentences.

    Args:
        query_embedding: Pre-computed query vector
        parent_text: Full parent chunk text

    Returns:
        Compressed string of top-N sentences in original order
    """
    sentences = split_sentences(parent_text)
    if len(sentences) <= SENTENCES_PER_CHUNK:
        return parent_text  # Already short enough

    # Embed all sentences
    sentence_embeddings = embed_texts(sentences)

    # Score each sentence vs query
    scored = [
        (i, compute_cosine_similarity(query_embedding, sent_emb), sent)
        for i, (sent, sent_emb) in enumerate(zip(sentences, sentence_embeddings))
    ]

    # Keep top-N by score
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:SENTENCES_PER_CHUNK]

    # Restore original order
    top_sorted = sorted(top, key=lambda x: x[0])
    return " ".join(s for _, _, s in top_sorted)


def compress_context(query_embedding: list[float], chunks: list[dict]) -> str:
    """
    Compress and concatenate parent chunks for LLM generation context.

    Args:
        query_embedding: Query vector for sentence-level scoring
        chunks: Reranked chunk dicts with 'parent_text' field

    Returns:
        Single compressed context string within MAX_CONTEXT_CHARS limit
    """
    parts = []
    total_chars = 0

    for i, chunk in enumerate(chunks):
        parent_text = chunk.get("parent_text", chunk.get("text", ""))
        compressed = compress_chunk(query_embedding, parent_text)

        source = chunk.get("source_filename", "Document")
        section = f"[Source: {source}]\n{compressed}"

        if total_chars + len(section) > MAX_CONTEXT_CHARS:
            break  # Stop adding chunks if context limit exceeded

        parts.append(section)
        total_chars += len(section)

    context = "\n\n---\n\n".join(parts)
    logger.info(
        "Context compressed",
        chunks_in=len(chunks),
        chunks_used=len(parts),
        total_chars=total_chars,
    )
    return context
