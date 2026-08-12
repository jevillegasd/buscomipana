import hashlib
import hmac
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.analytics import PingAnalyticsEvent
from app.models.ping import Ping

settings = get_settings()


def _hmac(value: uuid.UUID, *, pepper: str | None = None) -> str:
    key = (pepper or settings.analytics_pepper).encode("utf-8")
    return hmac.new(key, str(value).encode("utf-8"), hashlib.sha256).hexdigest()


def compute_subject_hash(user_id: uuid.UUID, *, pepper: str | None = None) -> str:
    """HMAC-SHA256(user_id, pepper). The pepper lives outside this database
    (env var / secrets manager), so a dump of ping_analytics_events alone cannot
    be reversed to identify a subject, even by someone with full DB access."""
    return _hmac(user_id, pepper=pepper)


def compute_ping_ref_hash(ping_id: uuid.UUID, *, pepper: str | None = None) -> str:
    """HMAC-SHA256(ping_id, pepper) -- a collision-free join key so
    record_pong_latency() can find the exact analytics row to update, without
    storing ping_id itself (which would let anyone with DB access join straight
    back to pings.subject_user_id, defeating the anonymization)."""
    return _hmac(ping_id, pepper=pepper)


async def anonymize_ping(db: AsyncSession, *, ping: Ping) -> PingAnalyticsEvent:
    event = PingAnalyticsEvent(
        subject_hash=compute_subject_hash(ping.subject_user_id),
        ping_ref_hash=compute_ping_ref_hash(ping.id),
        pepper_version=settings.analytics_pepper_version,
        status=ping.status,
        channel=ping.channel,
        is_proxy=ping.is_proxy,
        latitude=ping.latitude,
        longitude=ping.longitude,
        ping_created_at=ping.created_at,
    )
    db.add(event)
    await db.flush()
    return event


async def record_pong_latency(db: AsyncSession, *, ping: Ping, pong_created_at: datetime) -> None:
    result = await db.execute(
        select(PingAnalyticsEvent).where(PingAnalyticsEvent.ping_ref_hash == compute_ping_ref_hash(ping.id))
    )
    event = result.scalar_one_or_none()
    if event is None or event.first_pong_latency_seconds is not None:
        return

    latency = (pong_created_at - ping.created_at).total_seconds()
    event.first_pong_latency_seconds = max(0, int(latency))
    await db.flush()
