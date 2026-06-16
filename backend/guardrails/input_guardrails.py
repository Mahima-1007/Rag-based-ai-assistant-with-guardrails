"""
guardrails/input_guardrails.py — Multi-layer input validation and safety checks.

LAYERS (applied in order):
  1. Length validation      — reject empty or excessively long queries
  2. Regex injection check  — detect common prompt injection patterns
  3. Jailbreak detection    — detect known jailbreak phrases
  4. Harmful query check    — detect requests for harmful content
  5. PII detection          — flag/log PII in user queries

WHY ORDERED LAYERS:
  Cheap checks (regex) run first to short-circuit expensive ones (Presidio NER).
  If any layer fails, the request is rejected before hitting the RAG pipeline.
"""
import re
from dataclasses import dataclass

from guardrails.presidio_service import detect_pii
from monitoring.logger import get_logger

logger = get_logger(__name__)

# ── Configurable limits ──────────────────────────────────────────────────────────
MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 2000

# ── Prompt injection patterns ────────────────────────────────────────────────────
INJECTION_PATTERNS = [
    re.compile(r"ignore (previous|all|above|prior) instructions?", re.IGNORECASE),
    re.compile(r"disregard (your|the) (system|previous|original) prompt", re.IGNORECASE),
    re.compile(r"you are now (a|an|my)", re.IGNORECASE),
    re.compile(r"act as (if you are|a|an)", re.IGNORECASE),
    re.compile(r"forget (everything|all|your instructions)", re.IGNORECASE),
    re.compile(r"new persona", re.IGNORECASE),
    re.compile(r"pretend (you|to be)", re.IGNORECASE),
    re.compile(r"do anything now", re.IGNORECASE),
    re.compile(r"DAN mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"override (safety|restrictions|guidelines)", re.IGNORECASE),
]

# ── Jailbreak trigger phrases ────────────────────────────────────────────────────
JAILBREAK_PHRASES = [
    "developer mode",
    "sudo mode",
    "unrestricted mode",
    "bypass safety",
    "disable filters",
    "uncensored",
    "no restrictions",
    "respond without limitations",
]

# ── Harmful content keywords ─────────────────────────────────────────────────────
HARMFUL_KEYWORDS = [
    r"\bhow to make\b.{0,30}\b(bomb|explosive|weapon|poison|virus|malware)\b",
    r"\bsynthesi[sz]e\b.{0,30}\b(drug|meth|fentanyl|chemical weapon)\b",
    r"\bhack into\b",
    r"\bsteal (credentials|passwords|data)\b",
    r"\bchild (pornography|exploitation|abuse)\b",
    r"\bsuicide (method|instructions|how to)\b",
]
HARMFUL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in HARMFUL_KEYWORDS]


@dataclass
class GuardrailResult:
    is_safe: bool
    triggered_layer: str | None = None
    reason: str | None = None
    pii_detected: bool = False
    sanitized_query: str | None = None


def run_input_guardrails(query: str) -> GuardrailResult:
    """
    Run all input guardrail checks against the user query.

    Returns:
        GuardrailResult — is_safe=False means reject the request.
    """
    # ── Layer 1: Length check ────────────────────────────────────────────────────
    stripped = query.strip()
    if len(stripped) < MIN_QUERY_LENGTH:
        return GuardrailResult(
            is_safe=False,
            triggered_layer="length_check",
            reason="Query is too short. Please provide a meaningful question.",
        )

    if len(stripped) > MAX_QUERY_LENGTH:
        return GuardrailResult(
            is_safe=False,
            triggered_layer="length_check",
            reason=f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters.",
        )

    # ── Layer 2: Prompt injection ────────────────────────────────────────────────
    for pattern in INJECTION_PATTERNS:
        if pattern.search(stripped):
            logger.warning("Prompt injection detected", pattern=pattern.pattern[:50])
            return GuardrailResult(
                is_safe=False,
                triggered_layer="prompt_injection",
                reason="Prompt injection attempt detected. Request blocked.",
            )

    # ── Layer 3: Jailbreak detection ─────────────────────────────────────────────
    lower_query = stripped.lower()
    for phrase in JAILBREAK_PHRASES:
        if phrase in lower_query:
            logger.warning("Jailbreak attempt detected", phrase=phrase)
            return GuardrailResult(
                is_safe=False,
                triggered_layer="jailbreak",
                reason="Jailbreak attempt detected. Request blocked.",
            )

    # ── Layer 4: Harmful content ─────────────────────────────────────────────────
    for pattern in HARMFUL_PATTERNS:
        if pattern.search(stripped):
            logger.warning("Harmful query detected")
            return GuardrailResult(
                is_safe=False,
                triggered_layer="harmful_content",
                reason="This query has been flagged as potentially harmful and cannot be processed.",
            )

    # ── Layer 5: PII detection (log only — don't block, but flag) ───────────────
    pii_hits = detect_pii(stripped)
    pii_detected = len(pii_hits) > 0

    if pii_detected:
        logger.warning("PII detected in user query", types=[h["entity_type"] for h in pii_hits])

    return GuardrailResult(
        is_safe=True,
        pii_detected=pii_detected,
        sanitized_query=stripped,
    )
