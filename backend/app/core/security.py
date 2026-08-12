import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# argon2 is used for OTP codes (low-entropy, 6 digits) where a slow, salted hash
# matters. Refresh tokens are high-entropy random strings, so a fast sha256 digest
# is sufficient and avoids unnecessary CPU cost on every refresh.
_ph = PasswordHasher()


def hash_otp_code(code: str) -> str:
    return _ph.hash(code)


def verify_otp_code(code: str, code_hash: str) -> bool:
    try:
        return _ph.verify(code_hash, code)
    except VerifyMismatchError:
        return False


def generate_otp_code(length: int | None = None) -> str:
    length = length or settings.otp_code_length
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(*, user_id: str, role: str) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_ttl_days)


def ensure_aware(dt: datetime) -> datetime:
    """SQLite (used in unit tests) drops tzinfo on round-trip; Postgres (used in
    prod) preserves it. Normalize to UTC-aware so comparisons work on both."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
