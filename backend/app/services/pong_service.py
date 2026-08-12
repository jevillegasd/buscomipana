import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Channel, PongAudience
from app.models.ping import Ping, Pong
from app.services import analytics_service


class PongError(Exception):
    pass


class PingNotFoundForPong(PongError):
    pass


async def create_pong(
    db: AsyncSession,
    *,
    ping_id: uuid.UUID,
    responder_user_id: uuid.UUID,
    message: str | None,
    audience: PongAudience,
    channel: Channel = Channel.web,
) -> Pong:
    ping_result = await db.execute(select(Ping).where(Ping.id == ping_id))
    ping = ping_result.scalar_one_or_none()
    if ping is None:
        raise PingNotFoundForPong(str(ping_id))

    pong = Pong(
        ping_id=ping_id,
        responder_user_id=responder_user_id,
        message=message,
        audience=audience,
        channel=channel,
    )
    db.add(pong)
    await db.flush()

    # Only the first pong sets latency -- record_pong_latency() is a no-op once
    # the analytics row already has a value.
    await analytics_service.record_pong_latency(db, ping=ping, pong_created_at=pong.created_at)

    return pong


async def list_pongs_for_ping(db: AsyncSession, *, ping_id: uuid.UUID) -> list[Pong]:
    result = await db.execute(select(Pong).where(Pong.ping_id == ping_id).order_by(Pong.created_at.asc()))
    return list(result.scalars().all())
