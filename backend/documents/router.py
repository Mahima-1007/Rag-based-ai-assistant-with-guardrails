"""
documents/router.py — FastAPI routes for document management.

Routes:
  POST   /documents/upload      — Upload PDF/DOCX/TXT (triggers background ingestion)
  GET    /documents/list         — List authenticated user's documents
  GET    /documents/{id}         — Get single document metadata
  DELETE /documents/{id}         — Delete document + Qdrant vectors
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from auth.models import User
from database import get_db
from dependencies import get_current_user
from documents.models import Document
from documents.schemas import (
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    UploadStatusResponse,
)
from documents.service import delete_document, list_documents, upload_document
from sqlalchemy import select

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=UploadStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document (PDF, DOCX, or TXT).
    Returns immediately with status='processing'.
    Ingestion (parse → chunk → embed → store) runs in the background.
    """
    doc = await upload_document(file, str(current_user.id), db, background_tasks)
    return UploadStatusResponse(
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status,
        message="Document accepted for processing. Check status via GET /documents/{id}",
    )


@router.get("/list", response_model=DocumentListResponse)
async def list_docs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all documents belonging to the current user."""
    docs = await list_documents(db, str(current_user.id))
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get metadata for a single document owned by the current user."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_doc(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a document and its associated Qdrant vectors."""
    await delete_document(db, str(document_id), str(current_user.id))
    return DocumentDeleteResponse(
        message="Document and all associated vectors deleted successfully",
        document_id=document_id,
    )
