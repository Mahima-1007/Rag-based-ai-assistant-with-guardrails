"""
auth/schemas.py — Pydantic request/response schemas for authentication.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ─── Request Schemas ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Response Schemas ───────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class MeResponse(BaseModel):
    user: UserResponse
