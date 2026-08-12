import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.gateways.base import GatewaySendResult
from app.models.enums import SmsOutboxPurpose, SmsOutboxStatus
from app.models.sms import SmsOutboxEntry


async def record_send_result(
    db: AsyncSession,
    *,
    to_phone_number: str,
    purpose: SmsOutboxPurpose,
    body: str,
    result: GatewaySendResult,
    related_ping_id: uuid.UUID | None = None,
    related_otp_id: uuid.UUID | None = None,
) -> SmsOutboxEntry:
    """Records the outcome of every outbound SMS (OTP or ping/pong notification) so
    a failed send isn't silently lost -- the Celery retry_failed_sms sweep
    (app/workers/tasks.py) re-attempts anything left in 'failed' status."""
    entry = SmsOutboxEntry(
        to_phone_number=to_phone_number,
        purpose=purpose,
        body=body,
        provider=result.provider,
        provider_message_id=result.provider_message_id or None,
        status=SmsOutboxStatus.sent if result.accepted else SmsOutboxStatus.failed,
        attempt_count=1,
        last_error=result.error,
        related_ping_id=related_ping_id,
        related_otp_id=related_otp_id,
    )
    db.add(entry)
    await db.flush()
    return entry
