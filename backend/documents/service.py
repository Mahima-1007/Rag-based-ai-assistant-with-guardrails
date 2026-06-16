"""
documents/service.py — Document ingestion orchestration.

Pipeline:
  Upload → Parse → Clean → Chunk (Parent-Child) → Embed → Upsert to Qdrant
  → Update PostgreSQL document record status

WHY ASYNC BACKGROUND TASK:
  Embedding large documents takes 2-30 seconds depending on size.
  We accept the upload instantly, update status to 'processing',
  then run ingestion as a FastAPI BackgroundTask so the HTTP response
  is returned immediately to the user.
"""
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis_client import invalidate_user_cache
from documents.chunking import chunk_document
from documents.embedding import embed_texts_async
from documents.models import Document
from documents.parsing import parse_document
from monitoring.logger import get_logger
from vector_db.qdrant_client import delete_document_vectors, upsert_chunks

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def validate_upload(file: UploadFile) -> str:
    """Validate file type and name. Returns file extension."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )
    return ext


async def ingest_document_background(
    file_bytes: bytes,
    filename: str,
    document_id: str,
    user_id: str,
    db_url: str,
) -> None:
    """
    Background task: parse → chunk → embed → store in Qdrant.
    Uses a fresh DB session since background tasks run outside request scope.
    """
    from database import AsyncSessionLocal
    from sqlalchemy import update

    async with AsyncSessionLocal() as db:
        try:
            # 1. Parse document
            pages = await parse_document(file_bytes, filename)
            if not pages:
                raise ValueError("Document produced no parseable text")

            # 2. Chunk into parent-child pairs
            chunks = chunk_document(pages, document_id, user_id, filename)
            if not chunks:
                raise ValueError("Document produced no chunks")

            # 3. Embed child chunks (with Redis embedding cache check)
            from cache.redis_client import cache_embedding, get_cached_embedding

            texts = [c.text for c in chunks]
            embeddings = []
            uncached_indices = []
            uncached_texts = []

            for i, text in enumerate(texts):
                cached = await get_cached_embedding(text)
                if cached:
                    embeddings.append(cached)
                else:
                    embeddings.append(None)
                    uncached_indices.append(i)
                    uncached_texts.append(text)

            if uncached_texts:
                new_embeddings = await embed_texts_async(uncached_texts)
                for idx, emb in zip(uncached_indices, new_embeddings):
                    embeddings[idx] = emb
                    await cache_embedding(texts[idx], emb)

            # 4. Build chunk dicts for Qdrant upsert
            chunk_dicts = [
                {
                    "chunk_id": chunk.chunk_id,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "document_id": chunk.document_id,
                    "user_id": chunk.user_id,
                    "text": chunk.text,
                    "parent_text": chunk.parent_text,
                    "chunk_index": chunk.chunk_index,
                    "source_filename": chunk.source_filename,
                    "page_number": chunk.page_number,
                    "embedding": embeddings[i],
                }
                for i, chunk in enumerate(chunks)
            ]

            # 5. Upsert to Qdrant
            count = await upsert_chunks(user_id, chunk_dicts)

            # 6. Update document status in PostgreSQL
            from vector_db.qdrant_client import collection_name
            coll = collection_name(user_id)

            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(
                    status="ready",
                    chunk_count=count,
                    qdrant_collection=coll,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

            # 7. Invalidate user caches so new doc is included in future retrievals
            await invalidate_user_cache(user_id)

            logger.info(
                "Document ingestion complete",
                document_id=document_id,
                chunk_count=count,
            )

        except Exception as e:
            logger.error("Document ingestion failed", document_id=document_id, error=str(e))
            from sqlalchemy import update
            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(status="failed", updated_at=datetime.now(timezone.utc))
            )
            await db.commit()


async def upload_document(
    file: UploadFile,
    user_id: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> Document:
    """
    Accept upload, create DB record, trigger background ingestion.
    Returns immediately with status='processing'.
    """
    ext = validate_upload(file)
    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50MB limit",
        )

    document = Document(
        user_id=uuid.UUID(user_id),
        filename=file.filename,
        file_type=ext,
        file_size=len(file_bytes),
        status="processing",
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)

    # Trigger background ingestion (non-blocking)
    from config import get_settings
    settings = get_settings()
    background_tasks.add_task(
        ingest_document_background,
        file_bytes,
        file.filename,
        str(document.id),
        user_id,
        settings.DATABASE_URL,
    )

    logger.info("Document upload accepted", document_id=str(document.id), filename=file.filename)
    return document


async def list_documents(db: AsyncSession, user_id: str) -> list[Document]:
    """Return all documents belonging to the authenticated user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == uuid.UUID(user_id))
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


async def delete_document(db: AsyncSession, document_id: str, user_id: str) -> None:
    """Delete document record from PostgreSQL and its vectors from Qdrant."""
    result = await db.execute(
        select(Document).where(
            Document.id == uuid.UUID(document_id),
            Document.user_id == uuid.UUID(user_id),
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete vectors from Qdrant
    await delete_document_vectors(user_id, document_id)

    # Delete PostgreSQL record
    await db.delete(doc)
    await db.flush()

    # Invalidate caches
    await invalidate_user_cache(user_id)
    logger.info("Document deleted", document_id=document_id)
