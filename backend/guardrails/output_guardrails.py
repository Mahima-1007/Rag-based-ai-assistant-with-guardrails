"""
guardrails/output_guardrails.py — Output safety filtering before sending to client.

LAYERS (applied in order):
  1. PII anonymization    — Presidio replaces PII with entity-type placeholders
  2. Harmful content regex — block responses containing explicit harmful instructions
  3. Toxic content filter — detect and reject toxic/offensive language

WHY OUTPUT GUARDRAILS:
  The LLM (even with grounded prompting) might:
  - Echo PII that was in the uploaded documents
  - Generate unexpected harmful content under edge cases
  These filters provide a safety net AFTER generation but BEFORE client delivery.
"""
import re
from dataclasses import dataclass

from guardrails.presidio_service import anonymize_text
from monitoring.logger import get_logger

logger = get_logger(__name__)


# ── Harmful output patterns ──────────────────────────────────────────────────────
HARMFUL_OUTPUT_PATTERNS = [
    re.compile(r"\b(step[\s\-]by[\s\-]step|instructions)\b.{0,50}\b(bomb|weapon|explosive|poison)\b", re.IGNORECASE),
    re.compile(r"\bhow to (make|create|synthesize|build)\b.{0,30}\b(drug|meth|fentanyl)\b", re.IGNORECASE),
    re.compile(r"\bkill\b.{0,20}\b(yourself|someone|people)\b", re.IGNORECASE),
]

# ── Toxic content patterns ───────────────────────────────────────────────────────
TOXIC_PATTERNS = [
    re.compile(r"\b(f[u\*]ck|sh[i\*]t|c[u\*]nt|n[i\*]gg[a\*]r)\b", re.IGNORECASE),
    re.compile(r"\b(racist|sexist|homophobic)\b.{0,30}\b(slur|attack|remark)\b", re.IGNORECASE),
]


@dataclass
class OutputGuardrailResult:
    is_safe: bool
    sanitized_text: str
    pii_anonymized: bool = False
    harmful_detected: bool = False
    toxic_detected: bool = False
    blocked_reason: str | None = None


def run_output_guardrails(response_text: str) -> OutputGuardrailResult:
    """
    Apply all output safety layers to a generated LLM response.

    Args:
        response_text: Raw LLM response string

    Returns:
        OutputGuardrailResult — if is_safe=False, replace with safe fallback message.
    """
    # ── Layer 1: PII anonymization ───────────────────────────────────────────────
    original_text = response_text
    sanitized = anonymize_text(response_text)
    pii_anonymized = sanitized != original_text
    if pii_anonymized:
        logger.warning("PII anonymized in LLM output")

    # ── Layer 2: Harmful content check ──────────────────────────────────────────
    for pattern in HARMFUL_OUTPUT_PATTERNS:
        if pattern.search(sanitized):
            logger.error("Harmful content detected in LLM output — blocking response")
            return OutputGuardrailResult(
                is_safe=False,
                sanitized_text="I cannot provide this information as it may be harmful.",
                harmful_detected=True,
                blocked_reason="harmful_content",
            )

    # ── Layer 3: Toxic content check ─────────────────────────────────────────────
    for pattern in TOXIC_PATTERNS:
        if pattern.search(sanitized):
            logger.warning("Toxic content detected in LLM output — blocking response")
            return OutputGuardrailResult(
                is_safe=False,
                sanitized_text="The generated response contained inappropriate content and has been blocked.",
                toxic_detected=True,
                blocked_reason="toxic_content",
            )

    return OutputGuardrailResult(
        is_safe=True,
        sanitized_text=sanitized,
        pii_anonymized=pii_anonymized,
    )
