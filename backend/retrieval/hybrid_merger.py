"""
retrieval/hybrid_merger.py — Reciprocal Rank Fusion (RRF) merger.

WHY RRF:
  Semantic and BM25 return different ranking orders with incompatible scores.
  RRF normalizes both into a single unified ranking without requiring
  score calibration — proven effective in information retrieval research.

FORMULA:
  RRF(d) = Σ 1 / (k + rank_i(d))
  where k=60 is a smoothing constant, rank_i is position in each list.
"""
from monitoring.logger import get_logger

logger = get_logger(__name__)

RRF_K = 60  # Standard RRF smoothing constant


def reciprocal_rank_fusion(
    semantic_results: list[dict],
    bm25_results: list[dict],
    top_k: int = 20,
) -> list[dict]:
    """
    Merge semantic and BM25 results using Reciprocal Rank Fusion.

    Args:
        semantic_results: Chunks from Qdrant semantic search (with 'semantic_score')
        bm25_results: Chunks from BM25 keyword search (with 'bm25_score')
        top_k: Number of merged results to return

    Returns:
        Merged and re-ranked list of chunk dicts with 'rrf_score' added
    """
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    # Score from semantic ranking
    for rank, chunk in enumerate(semantic_results):
        chunk_id = chunk.get("chunk_id", "")
        if not chunk_id:
            continue
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        chunk_map[chunk_id] = chunk

    # Score from BM25 ranking
    for rank, chunk in enumerate(bm25_results):
        chunk_id = chunk.get("chunk_id", "")
        if not chunk_id:
            continue
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        if chunk_id not in chunk_map:
            chunk_map[chunk_id] = chunk

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    merged = []
    for chunk_id in sorted_ids[:top_k]:
        chunk = chunk_map[chunk_id].copy()
        chunk["rrf_score"] = round(rrf_scores[chunk_id], 6)
        merged.append(chunk)

    logger.info(
        "RRF merge complete",
        semantic_count=len(semantic_results),
        bm25_count=len(bm25_results),
        merged_count=len(merged),
    )
    return merged
