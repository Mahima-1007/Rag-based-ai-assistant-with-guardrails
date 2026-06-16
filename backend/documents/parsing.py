"""
documents/parsing.py — Document parsing using LangChain loaders.

Supported formats:
  - PDF   → PyPDFLoader
  - DOCX  → Docx2txtLoader
  - TXT   → TextLoader

Returns a list of LangChain Document objects with page_content and metadata.
"""
import os
import tempfile
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, TextLoader
from langchain_community.document_loaders import PyPDFLoader

from monitoring.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_TYPES = {"pdf", "docx", "txt"}


async def parse_document(file_bytes: bytes, filename: str) -> list:
    """
    Parse uploaded document bytes into LangChain Document chunks.

    Args:
        file_bytes: Raw bytes of the uploaded file
        filename: Original filename (used to detect file type)

    Returns:
        List of LangChain Document objects

    Raises:
        ValueError: If file type is unsupported
    """
    ext = Path(filename).suffix.lower().lstrip(".")

    if ext not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported file type: .{ext}. Allowed: {SUPPORTED_TYPES}")

    # Write to a temp file — LangChain loaders require file paths
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        logger.info("Parsing document", filename=filename, ext=ext, size_bytes=len(file_bytes))

        if ext == "pdf":
            loader = PyPDFLoader(tmp_path)
        elif ext == "docx":
            loader = Docx2txtLoader(tmp_path)
        elif ext == "txt":
            loader = TextLoader(tmp_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported: {ext}")

        pages = loader.load()
        logger.info("Document parsed", filename=filename, page_count=len(pages))
        return pages

    finally:
        os.unlink(tmp_path)


def clean_text(text: str) -> str:
    """
    Clean extracted text:
      - Remove excessive whitespace
      - Normalize line breaks
      - Strip null bytes
    """
    import re
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
