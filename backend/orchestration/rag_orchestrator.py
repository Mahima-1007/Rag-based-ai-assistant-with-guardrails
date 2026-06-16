"""
orchestration/rag_orchestrator.py — Full custom RAG pipeline coordinator.

THIS IS THE HEART OF THE SYSTEM. No LangChain chains or agents.
Custom FastAPI orchestration that coordinates every layer:

PIPELINE:
  1.  Input Guardrails        → reject harmful/injected queries
  2.  Retrieval Cache check   → return cached result if available
  3.  Retrieval Guardrails    → validate document ownership
  4.  Semantic Search         → Qdrant vector search
  5.  BM25 Search             → keyword retrieval on same corpus
  6.  RRF Merge               → combine semantic + BM25 rankings
  7.  CrossEncoder Reranking  → score and prune merged results
  8.  Retrieval Validation    → confidence scoring + ambiguity check
  9.  Decision Engine         → route to generate / clarify / insufficient
  10. Memory Loading          → conversation history injection
  11. Context Compression     → sentence-level compression of parent chunks
  12. Prompt Building         → LangChain PromptTemplate formatting
  13. LLM Streaming           → Groq/Mixtral token streaming
  14. Hallucination Check     → post-generation grounding validation
  15. Output Guardrails       → PII, harmful, toxic content filtering
  16. Cache storage           → cache response for future identical queries
  17. Metrics logging         → persist request metrics to monitoring_logs
"""
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis_client import cache_response, get_cached_response
from decision_engine.engine import DecisionType, make_decision
from documents.embedding import embed_single_async
from guardrails.input_guardrails import run_input_guardrails
from guardrails.output_guardrails import run_output_guardrails
from guardrails.retrieval_guardrails import (
    get_user_document_ids,
    validate_chunk_ownership,
    validate_document_ownership,
)
from hallucination.validator import HALLUCINATION_FALLBACK, validate_answer_grounding
from llm.groq_client import generate_response, stream_response
from llm.memory_manager import get_conversation_memory
from llm.prompt_builder import build_clarification_prompt, build_prompt
from monitoring.logger import get_logger
from monitoring.metrics import RequestMetrics, log_request_metrics
from retrieval.bm25_search import run_bm25_search
from retrieval.context_compression import compress_context
from retrieval.hybrid_merger import reciprocal_rank_fusion
from retrieval.reranking import rerank_chunks
from retrieval.semantic_search import run_semantic_search
from validation.retrieval_validator import validate_retrieval

logger = get_logger(__name__)


@dataclass
class OrchestratorContext:
    """Carries pipeline state through orchestration steps."""
    user_id: str
    session_id: str
    query: str
    document_ids: list[str]
    start_time: float
    query_embedding: list[float] | None = None
    semantic_results: list[dict] | None = None
    bm25_results: list[dict] | None = None
    merged_results: list[dict] | None = None
    reranked_chunks: list[dict] | None = None
    compressed_context: str = ""
    final_answer: str = ""
    confidence_level: str = "LOW"
    confidence_score: float = 0.0
    decision_type: str = "insufficient"
    guardrail_triggered: bool = False
    hallucination_detected: bool = False
    clarification_question: str | None = None
    sources: list[dict] | None = None


async def run_rag_pipeline(
    query: str,
    user_id: str,
    session_id: str,
    db: AsyncSession,
    document_ids: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Main RAG pipeline — yields SSE-formatted token strings for streaming.

    SSE format:
      data: {"type": "metadata", ...}   ← pipeline metadata (first event)
      data: {"type": "token", "text": "..."} ← each token
      data: {"type": "done", ...}       ← completion event
      data: {"type": "error", ...}      ← error event
    """
    import json

    ctx = OrchestratorContext(
        user_id=user_id,
        session_id=session_id,
        query=query,
        document_ids=document_ids or [],
        start_time=time.monotonic(),
    )

    metrics = RequestMetrics(user_id=user_id, session_id=session_id)

    try:
        # ── STEP 1: Input Guardrails ─────────────────────────────────────────────
        guard_result = run_input_guardrails(query)
        if not guard_result.is_safe:
            metrics.guardrail_triggered = True
            yield _sse_json("error", {"message": guard_result.reason, "layer": guard_result.triggered_layer})
            await _log_metrics(db, metrics, start_time=ctx.start_time)
            return

        if guard_result.pii_detected:
            metrics.guardrail_triggered = True

        sanitized_query = guard_result.sanitized_query or query

        # ── STEP 2: Response Cache Check ────────────────────────────────────────
        cached = await get_cached_response(user_id, sanitized_query)
        if cached:
            yield _sse_json("metadata", {
                "confidence_level": cached.get("confidence_level", "HIGH"),
                "confidence_score": cached.get("confidence_score", 1.0),
                "sources": cached.get("sources", []),
                "from_cache": True,
            })
            yield _sse_json("token", {"text": cached.get("answer", "")})
            yield _sse_json("done", {"from_cache": True})
            return

        # ── STEP 3: Retrieval Guardrails — document ownership ───────────────────
        if ctx.document_ids:
            ctx.document_ids = await validate_document_ownership(db, ctx.document_ids, user_id)
        else:
            ctx.document_ids = await get_user_document_ids(db, user_id)

        if not ctx.document_ids:
            yield _sse_json("error", {"message": "No documents found. Please upload documents first."})
            metrics.failed_retrieval = True
            await _log_metrics(db, metrics, start_time=ctx.start_time)
            return

        # ── STEP 4: Query Embedding ──────────────────────────────────────────────
        ctx.query_embedding = await embed_single_async(sanitized_query)

        # ── STEP 5: Semantic Search ──────────────────────────────────────────────
        ctx.semantic_results = await run_semantic_search(
            query=sanitized_query,
            user_id=user_id,
            top_k=20,
            document_ids=ctx.document_ids,
        )

        # ── STEP 6: BM25 Keyword Search ─────────────────────────────────────────
        ctx.bm25_results = await run_bm25_search(
            query=sanitized_query,
            user_id=user_id,
            corpus=ctx.semantic_results,
            top_k=20,
        )

        # ── STEP 7: RRF Merge ────────────────────────────────────────────────────
        ctx.merged_results = reciprocal_rank_fusion(
            semantic_results=ctx.semantic_results,
            bm25_results=ctx.bm25_results,
            top_k=20,
        )

        # ── STEP 8: Post-retrieval chunk ownership validation ────────────────────
        ctx.merged_results = validate_chunk_ownership(ctx.merged_results, user_id)

        # ── STEP 9: CrossEncoder Reranking ───────────────────────────────────────
        ctx.reranked_chunks = await rerank_chunks(
            query=sanitized_query,
            chunks=ctx.merged_results,
        )

        # ── STEP 10: Retrieval Validation ────────────────────────────────────────
        validation = validate_retrieval(
            query=sanitized_query,
            chunks=ctx.reranked_chunks,
            query_embedding=ctx.query_embedding,
        )
        metrics.retrieval_precision = validation.top_score
        metrics.reranker_score = validation.avg_score
        metrics.confidence_level = "LOW"

        # ── STEP 11: Decision Engine ─────────────────────────────────────────────
        decision = make_decision(validation, sanitized_query)
        ctx.confidence_level = decision.confidence_level
        ctx.confidence_score = decision.confidence_score
        ctx.decision_type = decision.decision.value
        metrics.confidence_level = ctx.confidence_level
        # Note: metadata SSE event is emitted later, after all routing decisions

        # ── STEP 12: Route by Decision ───────────────────────────────────────────
        if decision.decision == DecisionType.INSUFFICIENT:
            metrics.failed_retrieval = True
            # Emit metadata before returning insufficient
            ctx.sources = _build_sources(ctx.reranked_chunks)
            yield _sse_json("metadata", {
                "confidence_level": ctx.confidence_level,
                "confidence_score": round(ctx.confidence_score, 3),
                "decision": ctx.decision_type,
                "sources": ctx.sources,
            })
            yield _sse_json("token", {"text": decision.reason})
            yield _sse_json("done", {})
            await _log_metrics(db, metrics, start_time=ctx.start_time)
            return

        if decision.decision == DecisionType.RETRY:
            # Attempt one retry with a broader search (no document_id filter)
            ctx.semantic_results = await run_semantic_search(
                query=sanitized_query, user_id=user_id, top_k=20
            )
            ctx.reranked_chunks = await rerank_chunks(query=sanitized_query, chunks=ctx.semantic_results)
            validation = validate_retrieval(sanitized_query, ctx.reranked_chunks, ctx.query_embedding)
            decision = make_decision(validation, sanitized_query)
            ctx.confidence_level = decision.confidence_level
            ctx.confidence_score = decision.confidence_score
            ctx.decision_type = decision.decision.value
            metrics.confidence_level = ctx.confidence_level

            if decision.decision in (DecisionType.INSUFFICIENT, DecisionType.RETRY):
                metrics.failed_retrieval = True
                ctx.sources = _build_sources(ctx.reranked_chunks)
                yield _sse_json("metadata", {
                    "confidence_level": "LOW",
                    "confidence_score": round(ctx.confidence_score, 3),
                    "decision": ctx.decision_type,
                    "sources": ctx.sources,
                })
                yield _sse_json("token", {"text": HALLUCINATION_FALLBACK})
                yield _sse_json("done", {})
                await _log_metrics(db, metrics, start_time=ctx.start_time)
                return

        if decision.decision == DecisionType.CLARIFY:
            metrics.clarification_requested = True
            clarification = decision.clarification_question or "Could you please clarify your question?"
            ctx.sources = _build_sources(ctx.reranked_chunks)
            yield _sse_json("metadata", {
                "confidence_level": ctx.confidence_level,
                "confidence_score": round(ctx.confidence_score, 3),
                "decision": ctx.decision_type,
                "sources": ctx.sources,
            })
            yield _sse_json("token", {"text": clarification})
            yield _sse_json("done", {"clarification": True})
            await _log_metrics(db, metrics, start_time=ctx.start_time)
            return

        # Emit metadata for GENERATE path — now after all routing decisions
        ctx.sources = _build_sources(ctx.reranked_chunks)
        yield _sse_json("metadata", {
            "confidence_level": ctx.confidence_level,
            "confidence_score": round(ctx.confidence_score, 3),
            "decision": ctx.decision_type,
            "sources": ctx.sources,
        })

        # ── STEP 13: Memory Loading ──────────────────────────────────────────────
        memory = await get_conversation_memory(db, session_id)

        # ── STEP 14: Context Compression ────────────────────────────────────────
        ctx.compressed_context = compress_context(ctx.query_embedding, ctx.reranked_chunks)

        from guardrails.presidio_service import anonymize_text
        ctx.compressed_context = anonymize_text(ctx.compressed_context)

        # ── STEP 15: Prompt Building ─────────────────────────────────────────────
        prompt = build_prompt(
            context=ctx.compressed_context,
            question=sanitized_query,
            memory=memory,
        )

        # ── STEP 16: Streaming Generation ────────────────────────────────────────
        full_answer_parts = []
        async for token in stream_response(prompt):
            full_answer_parts.append(token)
            yield _sse_json("token", {"text": token})

        ctx.final_answer = "".join(full_answer_parts)

        # ── STEP 17: Hallucination Validation ────────────────────────────────────
        hall_result = validate_answer_grounding(ctx.final_answer, ctx.reranked_chunks)
        if not hall_result.is_grounded:
            metrics.hallucination_detected = True
            # Attempt regeneration once
            ctx.final_answer = await generate_response(prompt)
            hall_result2 = validate_answer_grounding(ctx.final_answer, ctx.reranked_chunks)
            if not hall_result2.is_grounded:
                ctx.final_answer = HALLUCINATION_FALLBACK
            # Re-stream the regenerated answer
            yield _sse_json("regenerated", {"text": ctx.final_answer})

        # ── STEP 18: Output Guardrails ───────────────────────────────────────────
        out_result = run_output_guardrails(ctx.final_answer)
        if not out_result.is_safe:
            metrics.guardrail_triggered = True
            ctx.final_answer = out_result.sanitized_text
        else:
            ctx.final_answer = out_result.sanitized_text

        # ── STEP 19: Cache Response ──────────────────────────────────────────────
        await cache_response(user_id, sanitized_query, {
            "answer": ctx.final_answer,
            "confidence_level": ctx.confidence_level,
            "confidence_score": ctx.confidence_score,
            "sources": ctx.sources,
        })

        yield _sse_json("done", {
            "hallucination_checked": True,
            "grounded": hall_result.is_grounded,
        })

    except Exception as e:
        logger.error("RAG pipeline error", error=str(e), user_id=user_id)
        yield _sse_json("error", {"message": "An internal error occurred. Please try again."})

    finally:
        # ── STEP 20: Metrics Logging ─────────────────────────────────────────────
        await _log_metrics(db, metrics, start_time=ctx.start_time)


def _sse_json(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event JSON payload."""
    import json
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"


def _build_sources(chunks: list[dict]) -> list[dict]:
    """Extract source document references from reranked chunks."""
    seen = set()
    sources = []
    for chunk in chunks:
        doc_id = chunk.get("document_id", "")
        if doc_id not in seen:
            seen.add(doc_id)
            sources.append({
                "document_id": doc_id,
                "filename": chunk.get("source_filename", "Unknown"),
                "reranker_score": round(chunk.get("reranker_score", 0.0), 3),
            })
    return sources


async def _log_metrics(
    db: AsyncSession, metrics: RequestMetrics, start_time: float
) -> None:
    """Compute latency and persist metrics."""
    metrics.latency_ms = int((time.monotonic() - start_time) * 1000)
    try:
        await log_request_metrics(db, metrics)
    except Exception as e:
        logger.error("Failed to log metrics", error=str(e))
