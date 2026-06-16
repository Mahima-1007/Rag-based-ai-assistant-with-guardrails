"""
monitoring/models.py — SQLAlchemy model for monitoring_logs.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

class MonitoringLog(Base):
    __tablename__ = "monitoring_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    retrieval_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    reranker_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    guardrail_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    hallucination_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    clarification_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_retrieval: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Use log_metadata in Python to avoid conflict with SQLAlchemy's Base.metadata
    log_metadata: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
