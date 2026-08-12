import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.gateways.base import InboundChannelEvent
from app.models.enums import Channel, SmsOutboxStatus
from app.models.sms import SmsOutboxEntry
from app.services import channel_ingest_service

router = APIRouter(prefix="/webhooks/infobip", tags=["webhooks"])

settings = get_settings()


def _verify_webhook_secret(x_webhook_secret: str | None) -> None:
    # Configured as a custom header on the Infobip inbound-SMS forwarding rule.
    # compare_digest instead of `!=` -- a naive comparison short-circuits on the
    # first mismatched byte, which leaks (via response timing) how many leading
    # characters of a guess were correct, letting the shared secret be brute-forced
    # byte-by-byte instead of all at once.
    if x_webhook_secret is None or not hmac.compare_digest(
        x_webhook_secret, settings.infobip_webhook_shared_secret
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")


@router.post("/sms/inbound", status_code=status.HTTP_200_OK)
async def infobip_sms_inbound(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    _verify_webhook_secret(x_webhook_secret)

    processed = 0
    for result in payload.get("results", []):
        from_number = result.get("from", "")
        if from_number and not from_number.startswith("+"):
            from_number = f"+{from_number}"
        event = InboundChannelEvent(
            channel=Channel.sms,
            from_phone_number=from_number,
            provider_message_id=result.get("messageId", ""),
            raw_text=result.get("text", ""),
            metadata=result,
        )
        if not event.provider_message_id:
            continue
        await channel_ingest_service.ingest(db, event=event)
        processed += 1

    await db.commit()
    return {"processed": processed}


@router.post("/sms/delivery-report", status_code=status.HTTP_200_OK)
async def infobip_sms_delivery_report(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    _verify_webhook_secret(x_webhook_secret)

    updated = 0
    for result in payload.get("results", []):
        message_id = result.get("messageId")
        delivery_status = (result.get("status") or {}).get("groupName", "").upper()
        if not message_id:
            continue
        entry_result = await db.execute(
            select(SmsOutboxEntry).where(SmsOutboxEntry.provider_message_id == message_id)
        )
        entry = entry_result.scalar_one_or_none()
        if entry is None:
            continue
        if delivery_status == "DELIVERED":
            entry.status = SmsOutboxStatus.delivered
        elif delivery_status in ("REJECTED", "EXPIRED", "UNDELIVERABLE"):
            entry.status = SmsOutboxStatus.failed
            entry.last_error = delivery_status
        updated += 1

    await db.commit()
    return {"updated": updated}


@router.post("/voice/inbound", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def infobip_voice_inbound():
    """Reserved for the IVR/fixed-line-call ping phase; not implemented in the MVP."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "IVR voice pings are not implemented yet")
