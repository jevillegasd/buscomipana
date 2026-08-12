import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RelationshipType, RelativeLinkStatus
from app.models.relative_link import RelativeLink
from app.models.user import User


class RelativeLinkError(Exception):
    pass


class TargetNotFound(RelativeLinkError):
    pass


class CannotLinkSelf(RelativeLinkError):
    pass


class LinkAlreadyExists(RelativeLinkError):
    pass


class NotAuthorizedForLink(RelativeLinkError):
    pass


async def request_link(
    db: AsyncSession, *, requester: User, target_phone_number: str, relationship_label: RelationshipType | None
) -> RelativeLink:
    result = await db.execute(
        select(User).where(User.phone_number == target_phone_number, User.deleted_at.is_(None))
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise TargetNotFound(target_phone_number)
    if target.id == requester.id:
        raise CannotLinkSelf()

    existing = await db.execute(
        select(RelativeLink).where(
            or_(
                (RelativeLink.requester_user_id == requester.id) & (RelativeLink.target_user_id == target.id),
                (RelativeLink.requester_user_id == target.id) & (RelativeLink.target_user_id == requester.id),
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise LinkAlreadyExists()

    link = RelativeLink(
        requester_user_id=requester.id,
        target_user_id=target.id,
        relationship_label=relationship_label,
        status=RelativeLinkStatus.pending,
    )
    db.add(link)
    await db.flush()
    return link


async def _get_link_for_user(db: AsyncSession, *, link_id: uuid.UUID, user_id: uuid.UUID) -> RelativeLink:
    result = await db.execute(select(RelativeLink).where(RelativeLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None or (link.requester_user_id != user_id and link.target_user_id != user_id):
        raise NotAuthorizedForLink()
    return link


async def respond_to_link(
    db: AsyncSession, *, user: User, link_id: uuid.UUID, accept: bool
) -> RelativeLink:
    link = await _get_link_for_user(db, link_id=link_id, user_id=user.id)
    if link.target_user_id != user.id or link.status != RelativeLinkStatus.pending:
        raise NotAuthorizedForLink()

    link.status = RelativeLinkStatus.accepted if accept else RelativeLinkStatus.declined
    link.responded_at = datetime.now(UTC)
    await db.flush()
    return link


async def revoke_link(db: AsyncSession, *, user: User, link_id: uuid.UUID) -> RelativeLink:
    link = await _get_link_for_user(db, link_id=link_id, user_id=user.id)
    link.status = RelativeLinkStatus.revoked
    link.responded_at = datetime.now(UTC)
    await db.flush()
    return link


async def list_links(
    db: AsyncSession, *, user: User, status_filter: RelativeLinkStatus | None = None
) -> list[RelativeLink]:
    query = select(RelativeLink).where(
        or_(RelativeLink.requester_user_id == user.id, RelativeLink.target_user_id == user.id)
    )
    if status_filter is not None:
        query = query.where(RelativeLink.status == status_filter)
    result = await db.execute(query.order_by(RelativeLink.requested_at.desc()))
    return list(result.scalars().all())
