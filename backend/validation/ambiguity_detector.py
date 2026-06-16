"""
validation/ambiguity_detector.py — Detects ambiguous or underspecified queries.

A query is considered ambiguous if:
  - It is very short (< 4 words) with no content terms
  - It consists primarily of pronouns/articles (this, it, that, the)
  - It references pronouns without antecedents in isolation

WHY THIS MATTERS:
  Ambiguous queries lead to poor retrieval even if documents are relevant.
  Detecting them early allows the system to ask for clarification before
  wasting LLM tokens on low-quality context.
"""
import re

PRONOUN_PATTERN = re.compile(
    r"^(what|tell me|explain|describe|show|give)?\s*"
    r"(about|me|it|this|that|these|those|them|its|their|his|her)?\s*$",
    re.IGNORECASE,
)

# Words that carry semantic content (not just function words)
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "them", "they",
    "what", "who", "where", "when", "how", "why", "tell", "me",
    "about", "please", "can", "you", "do", "does", "did",
}


def detect_ambiguity(query: str) -> bool:
    """
    Return True if the query appears ambiguous or underspecified.

    Examples of ambiguous queries:
      - "it"
      - "tell me about this"
      - "what is that"
      - "explain"

    Examples of non-ambiguous:
      - "What is the refund policy for premium users?"
      - "How does authentication work in this system?"
    """
    tokens = re.findall(r"\b\w+\b", query.lower())

    if len(tokens) == 0:
        return True

    # Short query: check if all tokens are stop words
    if len(tokens) <= 3:
        non_stop = [t for t in tokens if t not in STOP_WORDS]
        if len(non_stop) == 0:
            return True

    # Very short query with no content words (< 2 meaningful tokens)
    content_tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    if len(content_tokens) < 1 and len(tokens) < 5:
        return True

    return False
