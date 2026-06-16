"""
documents/chunking.py — Parent-Child semantic chunking strategy.

HOW IT WORKS:
  1. Split parsed document into large PARENT chunks (1000 tokens, 200 overlap)
     → These preserve surrounding context for answer generation
  2. Split each parent chunk into small CHILD chunks (256 tokens, 50 overlap)
     → These are embedded and used for retrieval precision

BENEFIT:
  - Retrieval uses child chunks (precise, focused)
  - Generation uses parent chunks (full context around the hit)
  - Reduces hallucination by providing adequate context to the LLM
"""
import uuid
from dataclasses import dataclass, field

from langchain.text_splitter import RecursiveCharacterTextSplitter

from config import get_settings
from documents.parsing import clean_text
from monitoring.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class ChildChunk:
    chunk_id: str
    parent_chunk_id: str
    document_id: str
    user_id: str
    text: str                  # Small chunk — used for embedding + retrieval
    parent_text: str           # Full parent chunk — used for LLM generation
    chunk_index: int
    source_filename: str
    page_number: int = 0
    metadata: dict = field(default_factory=dict)


def build_parent_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.PARENT_CHUNK_SIZE,
        chunk_overlap=settings.PARENT_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def build_child_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHILD_CHUNK_SIZE,
        chunk_overlap=settings.CHILD_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def chunk_document(
    pages: list,          # LangChain Document objects from parsing.py
    document_id: str,
    user_id: str,
    filename: str,
) -> list[ChildChunk]:
    """
    Apply Parent-Child chunking to a list of LangChain Document pages.

    Returns a flat list of ChildChunk objects ready for embedding.
    """
    parent_splitter = build_parent_splitter()
    child_splitter = build_child_splitter()

    # Concatenate all pages with their metadata
    full_texts = []
    page_map = {}  # track page numbers by text offset

    for page in pages:
        cleaned = clean_text(page.page_content)
        if cleaned:
            full_texts.append(cleaned)
            page_map[cleaned] = page.metadata.get("page", 0)

    combined_text = "\n\n".join(full_texts)

    # Step 1: Create parent chunks
    parent_texts = parent_splitter.split_text(combined_text)

    all_child_chunks: list[ChildChunk] = []
    child_index = 0

    logger.info(
        "Chunking document",
        document_id=document_id,
        parent_count=len(parent_texts),
    )

    for parent_text in parent_texts:
        parent_chunk_id = str(uuid.uuid4())

        # Step 2: Split each parent into children
        child_texts = child_splitter.split_text(parent_text)

        for child_text in child_texts:
            if len(child_text.strip()) < 20:
                continue  # Skip trivially small chunks

            chunk = ChildChunk(
                chunk_id=str(uuid.uuid4()),
                parent_chunk_id=parent_chunk_id,
                document_id=document_id,
                user_id=user_id,
                text=child_text.strip(),
                parent_text=parent_text.strip(),
                chunk_index=child_index,
                source_filename=filename,
                page_number=0,  # page tracking simplified for multi-page merge
            )
            all_child_chunks.append(chunk)
            child_index += 1

    logger.info(
        "Chunking complete",
        document_id=document_id,
        total_child_chunks=len(all_child_chunks),
    )
    return all_child_chunks
