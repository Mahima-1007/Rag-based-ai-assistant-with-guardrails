"""
auth/router.py — FastAPI router for all authentication endpoints.

Routes:
  POST /auth/register   — Register new user
  POST /auth/login      — Login and receive JWT pair
  POST /auth/refresh    — Refresh access token
  POST /auth/logout     — Revoke sessions
  GET  /auth/me         — Get current user profile
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from auth.service import login_user, logout_user, refresh_tokens, register_user
from database import get_db
from dependencies import get_current_user
from auth.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    user = await register_user(db, payload)
    return RegisterResponse(
        message="Account created successfully",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive access + refresh JWT tokens."""
    return await login_user(db, payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Use refresh token to obtain a new token pair (rotation)."""
    return await refresh_tokens(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke all sessions for the authenticated user."""
    await logout_user(db, str(current_user.id))


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return MeResponse(user=UserResponse.model_validate(current_user))
