import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ResponderCredentialStatus
from app.models.relative_link import ResponderCredential
from app.models.user import User


class ResponderError(Exception):
    pass


class AlreadyApplied(ResponderError):
    pass


class CredentialNotFound(ResponderError):
    pass


async def apply(
    db: AsyncSession, *, user: User, organization_name: str, credential_type: str, notes: str | None
) -> ResponderCredential:
    existing = await db.execute(select(ResponderCredential).where(ResponderCredential.user_id == user.id))
    if existing.scalar_one_or_none() is not None:
        raise AlreadyApplied()

    credential = ResponderCredential(
        user_id=user.id,
        organization_name=organization_name,
        credential_type=credential_type,
        notes=notes,
        status=ResponderCredentialStatus.pending,
    )
    db.add(credential)
    await db.flush()
    return credential


async def list_pending(db: AsyncSession) -> list[ResponderCredential]:
    result = await db.execute(
        select(ResponderCredential).where(ResponderCredential.status == ResponderCredentialStatus.pending)
    )
    return list(result.scalars().all())


async def _get(db: AsyncSession, *, user_id: uuid.UUID) -> ResponderCredential:
    result = await db.execute(select(ResponderCredential).where(ResponderCredential.user_id == user_id))
    credential = result.scalar_one_or_none()
    if credential is None:
        raise CredentialNotFound()
    return credential


async def verify(db: AsyncSession, *, user_id: uuid.UUID, admin: User) -> ResponderCredential:
    credential = await _get(db, user_id=user_id)
    credential.status = ResponderCredentialStatus.verified
    credential.verified_by_admin_id = admin.id
    credential.verified_at = datetime.now(UTC)
    await db.flush()
    return credential


async def revoke(db: AsyncSession, *, user_id: uuid.UUID, admin: User) -> ResponderCredential:
    credential = await _get(db, user_id=user_id)
    credential.status = ResponderCredentialStatus.revoked
    credential.verified_by_admin_id = admin.id
    await db.flush()
    return credential
