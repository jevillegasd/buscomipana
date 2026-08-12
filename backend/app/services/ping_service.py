import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Channel, PingStatus
from app.models.ping import Ping
from app.models.user import User
from app.schemas.ping import PingOut
from app.services import analytics_service, notification_service
from app.services.visibility_service import can_view_location


class PingError(Exception):
    pass


class SubjectNotFound(PingError):
    pass


class PingNotFound(PingError):
    pass


async def create_ping(
    db: AsyncSession,
    *,
    reported_by_user_id: uuid.UUID,
    subject_user_id: uuid.UUID | None,
    status: PingStatus,
    message: str | None,
    latitude: float | None,
    longitude: float | None,
    location_accuracy_m: int | None,
    channel: Channel,
    channel_metadata: dict | None = None,
) -> Ping:
    """The single entry point every channel (web, SMS, and later IVR/USSD) must
    funnel through. Channel-specific adapters normalize their input into this
    call's parameters -- none of them touch notification/analytics logic
    directly, so adding a channel never means touching this function."""
    resolved_subject_id = subject_user_id or reported_by_user_id

    if resolved_subject_id != reported_by_user_id:
        subject_result = await db.execute(select(User).where(User.id == resolved_subject_id))
        if subject_result.scalar_one_or_none() is None:
            raise SubjectNotFound(str(resolved_subject_id))

    ping = Ping(
        subject_user_id=resolved_subject_id,
        reported_by_user_id=reported_by_user_id,
        status=status,
        message=message,
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=location_accuracy_m,
        channel=channel,
        channel_metadata=channel_metadata or {},
    )
    db.add(ping)
    await db.flush()

    await notification_service.notify_ping(db, ping=ping)
    # Anonymization is awaited inline here (MVP simplicity, no Redis dependency
    # on the request path); app/workers/tasks.py:anonymize_ping wraps the same
    # logic for a production deployment that wants it off the request path.
    await analytics_service.anonymize_ping(db, ping=ping)

    return ping


async def get_ping(db: AsyncSession, *, ping_id: uuid.UUID) -> Ping:
    result = await db.execute(select(Ping).where(Ping.id == ping_id))
    ping = result.scalar_one_or_none()
    if ping is None:
        raise PingNotFound(str(ping_id))
    return ping


async def list_pings_for_subject(
    db: AsyncSession, *, subject_user_id: uuid.UUID, since=None, limit: int = 50
) -> list[Ping]:
    query = select(Ping).where(Ping.subject_user_id == subject_user_id)
    if since is not None:
        query = query.where(Ping.created_at >= since)
    query = query.order_by(Ping.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def serialize_ping(db: AsyncSession, *, ping: Ping, viewer_id: uuid.UUID) -> PingOut:
    show_location = await can_view_location(db, viewer_id=viewer_id, subject_id=ping.subject_user_id)
    return PingOut(
        id=ping.id,
        subject_user_id=ping.subject_user_id,
        reported_by_user_id=ping.reported_by_user_id,
        is_proxy=ping.is_proxy,
        status=ping.status,
        message=ping.message,
        latitude=float(ping.latitude) if show_location and ping.latitude is not None else None,
        longitude=float(ping.longitude) if show_location and ping.longitude is not None else None,
        location_accuracy_m=ping.location_accuracy_m if show_location else None,
        channel=ping.channel,
        created_at=ping.created_at,
    )
