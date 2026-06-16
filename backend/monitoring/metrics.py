"""
monitoring/metrics.py — In-process metrics tracking for the RAG pipeline.

Tracks:
  - retrieval_precision: avg reranker score of kept chunks
  - hallucination_rate:  fraction of responses flagged as hallucinated
  - latency_ms:          end-to-end response latency per request
  - reranker_effectiveness: chunks kept / chunks retrieved ratio
  - guardrail_trigger_rate: fraction of requests that triggered a guardrail
  - clarification_frequency: fraction of responses that asked for clarification
  - failed_retrieval_rate: fraction of queries with LOW confidence

WHY IN-PROCESS:
  Simple, zero-dependency metrics that can be flushed to PostgreSQL monitoring_logs.
  In production, swap with Prometheus client.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RequestMetrics:
    """Metrics captured for a single RAG request."""
    user_id: str
    session_id: str | None = None
    event_type: str = "rag_request"
    retrieval_precision: float | None = None
    reranker_score: float | None = None
    confidence_level: str | None = None
    latency_ms: int | None = None
    guardrail_triggered: bool = False
    hallucination_detected: bool = False
    clarification_requested: bool = False
    failed_retrieval: bool = False
    metadata: dict = field(default_factory=dict)


async def log_request_metrics(db: AsyncSession, metrics: RequestMetrics) -> None:
    """
    Persist request metrics to the monitoring_logs table.
    Called at the end of every RAG request.
    """
    import uuid
    from sqlalchemy import text

    query = text("""
        INSERT INTO monitoring_logs (
            id, user_id, session_id, event_type,
            retrieval_precision, reranker_score, confidence_level,
            latency_ms, guardrail_triggered, hallucination_detected,
            clarification_requested, failed_retrieval, metadata, created_at
        ) VALUES (
            :id, :user_id, :session_id, :event_type,
            :retrieval_precision, :reranker_score, :confidence_level,
            :latency_ms, :guardrail_triggered, :hallucination_detected,
            :clarification_requested, :failed_retrieval, :metadata, :created_at
        )
    """)

    try:
        await db.execute(
            query,
            {
                "id": str(uuid.uuid4()),
                "user_id": metrics.user_id,
                "session_id": metrics.session_id,
                "event_type": metrics.event_type,
                "retrieval_precision": metrics.retrieval_precision,
                "reranker_score": metrics.reranker_score,
                "confidence_level": metrics.confidence_level,
                "latency_ms": metrics.latency_ms,
                "guardrail_triggered": metrics.guardrail_triggered,
                "hallucination_detected": metrics.hallucination_detected,
                "clarification_requested": metrics.clarification_requested,
                "failed_retrieval": metrics.failed_retrieval,
                "metadata": str(metrics.metadata),
                "created_at": datetime.now(timezone.utc),
            },
        )
        logger.info("Metrics logged", user_id=metrics.user_id, confidence=metrics.confidence_level)
    except Exception as e:
        logger.error("Failed to log metrics", error=str(e))
