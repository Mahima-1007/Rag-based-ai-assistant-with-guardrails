"""
auth/service.py — Business logic for user registration, login, and token refresh.
All DB operations use async SQLAlchemy sessions.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_utils import create_access_token, create_refresh_token, decode_refresh_token
from auth.models import User, UserSession
from auth.password_utils import hash_password, verify_password
from auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from config import get_settings

settings = get_settings()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """Register a new user after checking for email/username conflicts."""
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, payload: LoginRequest) -> TokenResponse:
    """Authenticate user credentials and return JWT token pair."""
    user = await get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Persist refresh token in sessions table
    session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """Validate refresh token and issue a new token pair."""
    payload = decode_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Check token exists in DB (not revoked)
    result = await db.execute(
        select(UserSession).where(UserSession.refresh_token == refresh_token)
    )
    db_session = result.scalar_one_or_none()
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    user = await get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate: delete old session, issue new tokens
    await db.delete(db_session)

    token_data = {"sub": str(user.id), "email": user.email}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    new_session = UserSession(
        user_id=user.id,
        refresh_token=new_refresh,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_session)
    await db.flush()

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def logout_user(db: AsyncSession, user_id: str) -> None:
    """Revoke all active sessions for a user."""
    result = await db.execute(
        select(UserSession).where(UserSession.user_id == uuid.UUID(user_id))
    )
    sessions = result.scalars().all()
    for s in sessions:
        await db.delete(s)
    await db.flush()
