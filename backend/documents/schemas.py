"""
documents/schemas.py — Pydantic schemas for document upload and responses.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int | None
    status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class DocumentDeleteResponse(BaseModel):
    message: str
    document_id: UUID


class UploadStatusResponse(BaseModel):
    document_id: UUID
    filename: str
    status: str
    message: str
