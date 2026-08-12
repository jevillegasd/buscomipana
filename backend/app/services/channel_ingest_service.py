from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateways.base import InboundChannelEvent
from app.models.enums import PingStatus, PongAudience, SmsIntent
from app.models.sms import InboundSmsMessage
from app.models.user import User
from app.services import ping_service, pong_service


def parse_sms_intent(body: str) -> tuple[SmsIntent, dict]:
    normalized = body.strip().upper()
    if normalized in ("PING OK", "OK"):
        return SmsIntent.ping_ok, {}
    if normalized in ("PING SOS", "SOS"):
        return SmsIntent.ping_sos, {}
    if normalized.startswith("PONG"):
        parts = body.strip().split(maxsplit=2)
        if len(parts) >= 2:
            return SmsIntent.pong, {"target_phone": parts[1], "message": parts[2] if len(parts) > 2 else None}
    return SmsIntent.unrecognized, {}


async def ingest(db: AsyncSession, *, event: InboundChannelEvent) -> InboundSmsMessage:
    """Normalizes any inbound channel event (SMS today, IVR/USSD later) into the
    same ping_service.create_ping()/pong_service.create_pong() calls the web REST
    endpoints use. Idempotent on provider_message_id since SMS providers retry
    delivery of the same inbound message."""
    existing = await db.execute(
        select(InboundSmsMessage).where(InboundSmsMessage.provider_message_id == event.provider_message_id)
    )
    already = existing.scalar_one_or_none()
    if already is not None:
        return already

    sender_result = await db.execute(select(User).where(User.phone_number == event.from_phone_number))
    sender = sender_result.scalar_one_or_none()

    intent, parsed = parse_sms_intent(event.raw_text or "")
    resulting_ping_id = None

    if sender is None:
        intent = SmsIntent.unrecognized
    elif intent in (SmsIntent.ping_ok, SmsIntent.ping_sos):
        status = PingStatus.ok if intent == SmsIntent.ping_ok else PingStatus.distress
        ping = await ping_service.create_ping(
            db,
            reported_by_user_id=sender.id,
            subject_user_id=None,
            status=status,
            message=None,
            latitude=None,
            longitude=None,
            location_accuracy_m=None,
            channel=event.channel,
            channel_metadata=event.metadata or {},
        )
        resulting_ping_id = ping.id
    elif intent == SmsIntent.pong:
        target_result = await db.execute(select(User).where(User.phone_number == parsed["target_phone"]))
        target = target_result.scalar_one_or_none()
        if target is not None:
            latest_pings = await ping_service.list_pings_for_subject(db, subject_user_id=target.id, limit=1)
            if latest_pings:
                pong = await pong_service.create_pong(
                    db,
                    ping_id=latest_pings[0].id,
                    responder_user_id=sender.id,
                    message=parsed.get("message"),
                    audience=PongAudience.directed,
                    channel=event.channel,
                )
                resulting_ping_id = pong.ping_id
            else:
                intent = SmsIntent.unrecognized
        else:
            intent = SmsIntent.unrecognized

    inbound_message = InboundSmsMessage(
        provider_message_id=event.provider_message_id,
        from_phone_number=event.from_phone_number,
        body=event.raw_text or "",
        parsed_intent=intent,
        resulting_ping_id=resulting_ping_id,
        raw_payload=event.metadata or {},
    )
    db.add(inbound_message)
    await db.flush()
    return inbound_message
