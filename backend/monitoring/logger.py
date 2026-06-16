"""
monitoring/logger.py — Structured JSON logging using structlog.

WHY STRUCTURED LOGGING:
  - Machine-parseable JSON logs for production monitoring
  - Consistent fields across all modules (timestamp, level, module, event)
  - Easy to forward to ELK, Datadog, or CloudWatch
"""
import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog and standard library logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger for a module."""
    return structlog.get_logger(name)
