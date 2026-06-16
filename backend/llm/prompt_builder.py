"""
llm/prompt_builder.py — LangChain PromptTemplate for grounded RAG generation.

DESIGN PRINCIPLES:
  - ONLY answer from provided context (grounding instruction)
  - Explicit refusal when information is unavailable
  - Source citation instruction for transparency
  - Memory injection (last N conversation turns for coherence)

WHY LANGCHAIN PROMPTTEMPLATE (not f-strings):
  - Structured variable injection with validation
  - Easy to swap/version prompts without code changes
  - Consistent formatting across all LLM calls
"""
from langchain.prompts import PromptTemplate

# ── System prompt — grounded, conservative, citation-aware ───────────────────────
SYSTEM_PROMPT = """You are a strict document-retrieval assistant. You are NOT a general AI assistant.

ABSOLUTE RULES — VIOLATION IS NOT ALLOWED:
1. You MUST answer ONLY using information that is LITERALLY and EXPLICITLY written in the CONTEXT below.
2. If the CONTEXT does not contain the exact information needed to answer, say exactly: "I do not have enough information in the provided documents to answer this question."
3. Do NOT infer, guess, categorize, classify, expand, or elaborate beyond what is literally written.
4. Do NOT use your general knowledge under ANY circumstances, even if you think you know the answer.
5. Do NOT create lists, categories, or types of things unless those exact lists are written in the CONTEXT.
6. Do NOT say "Based on the context" and then add information not present in the context.
7. If the CONTEXT contains only a definition but the user asks for types, examples, or categories, say: "I do not have enough information in the provided documents to answer this question."
8. Be concise. Only quote or paraphrase what is literally written in the CONTEXT.

CONTEXT:
{context}

CONVERSATION HISTORY:
{memory}

USER QUESTION: {question}

ANSWER (using ONLY what is explicitly written in the CONTEXT above):"""

RAG_PROMPT = PromptTemplate(
    input_variables=["context", "memory", "question"],
    template=SYSTEM_PROMPT,
)


def build_prompt(context: str, question: str, memory: str = "") -> str:
    """
    Format the RAG prompt with context, question, and conversation memory.

    Args:
        context: Compressed and reranked document context
        question: User's sanitized query
        memory: Summarized conversation history (empty for first turn)

    Returns:
        Formatted prompt string ready for Groq API submission
    """
    return RAG_PROMPT.format(
        context=context if context else "No context available.",
        memory=memory if memory else "No prior conversation.",
        question=question,
    )


def build_clarification_prompt(question: str, clarification: str) -> str:
    """
    Build a minimal prompt for asking a clarification question.
    Does NOT include document context (no retrieval needed).
    """
    return (
        f"The user asked: \"{question}\"\n\n"
        f"Please ask the following clarification question politely:\n{clarification}"
    )
