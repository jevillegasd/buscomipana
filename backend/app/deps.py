import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import ResponderCredentialStatus, UserRole, UserStatus
from app.models.relative_link import ResponderCredential
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
settings = get_settings()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Bearer header first (mobile/API/test clients), falling back to the
    # HttpOnly cookie set for browser sessions -- see auth.py's _set_auth_cookies.
    token = credentials.credentials if credentials is not None else request.cookies.get(
        settings.access_token_cookie_name
    )
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or inactive")

    return user


async def require_responder(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    # Re-checked against the DB on every request (not a JWT claim) so a revoked
    # credential takes effect immediately rather than at next token refresh.
    if user.role == UserRole.admin:
        return user
    result = await db.execute(
        select(ResponderCredential).where(
            ResponderCredential.user_id == user.id,
            ResponderCredential.status == ResponderCredentialStatus.verified,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verified responder credential required")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user
