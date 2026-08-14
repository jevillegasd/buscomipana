from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateways.base import MAX_SMS_SEGMENT_CHARS, to_gsm7
from app.gateways.factory import get_gateway
from app.models.enums import PingStatus, RelativeLinkStatus, SmsOutboxPurpose
from app.models.ping import Ping
from app.models.relative_link import RelativeLink
from app.models.user import User
from app.services import sms_outbox_service


def render_ping_message(ping: Ping, subject_name: str, reporter_name: str | None) -> str:
    """Takes the full Ping row (never a stripped payload) so is_proxy can never be
    silently dropped between the DB row and the outbound message.

    Spanish: user-facing SMS copy, matching the labels already used in the
    frontend (see PING_STATUS_LABELS_ES in RelativesPage.tsx). The status
    line is built first and never truncated -- if ping.message is long
    enough that appending it would blow the single-segment budget, only the
    free-text tail gets clipped, never "NECESITA AYUDA" itself."""
    status_label = {"ok": "ESTÁ BIEN", "distress": "NECESITA AYUDA", "unknown": "ESTADO DESCONOCIDO"}[
        ping.status.value
    ]
    if ping.is_proxy:
        base = f"Reportado por {reporter_name or 'un pana'} en nombre de {subject_name}: {status_label}"
    else:
        base = f"{subject_name}: {status_label}"
    base = to_gsm7(base)[:MAX_SMS_SEGMENT_CHARS]

    if not ping.message:
        return base

    budget = MAX_SMS_SEGMENT_CHARS - len(base)
    if budget <= 0:
        return base
    return base + to_gsm7(f" - {ping.message}")[:budget]


async def _accepted_relative_ids(db: AsyncSession, *, subject_user_id) -> list:
    result = await db.execute(
        select(RelativeLink).where(
            RelativeLink.status == RelativeLinkStatus.accepted,
            or_(RelativeLink.requester_user_id == subject_user_id, RelativeLink.target_user_id == subject_user_id),
        )
    )
    links = result.scalars().all()
    return [
        link.target_user_id if link.requester_user_id == subject_user_id else link.requester_user_id
        for link in links
    ]


async def notify_ping(db: AsyncSession, *, ping: Ping) -> None:
    """Fans a distress ping out to the subject's accepted relatives by SMS.
    OK/unknown pings never fan out, and responders aren't notified here at
    all -- they'll get their own dedicated frontend/feed later instead of an
    SMS blast, both to limit SMS spend. MVP sends synchronously via the SMS
    gateway; step 8 moves this into a Celery task without changing this
    function's logic."""
    if ping.status != PingStatus.distress:
        return

    subject_result = await db.execute(select(User).where(User.id == ping.subject_user_id))
    subject = subject_result.scalar_one_or_none()
    if subject is None:
        return

    reporter_name = None
    if ping.is_proxy:
        reporter_result = await db.execute(select(User).where(User.id == ping.reported_by_user_id))
        reporter = reporter_result.scalar_one_or_none()
        reporter_name = reporter.full_name if reporter else None

    subject_name = subject.full_name or subject.phone_number
    message = render_ping_message(ping, subject_name, reporter_name)

    recipient_ids = set(await _accepted_relative_ids(db, subject_user_id=ping.subject_user_id))
    recipient_ids.discard(ping.subject_user_id)

    if not recipient_ids:
        return

    recipients_result = await db.execute(select(User).where(User.id.in_(recipient_ids)))
    gateway = get_gateway()
    for recipient in recipients_result.scalars().all():
        # Issue #10: phone_verified_at is only set once this account has
        # completed a real SMS-delivered OTP -- an account that hasn't
        # (possible for accounts created before that fix, via the
        # vulnerable email-any-address path) might not actually control this
        # number, so it must never receive someone else's status/location
        # data over SMS.
        if recipient.phone_verified_at is None:
            continue
        result = await gateway.send_sms(
            recipient.phone_number, message, idempotency_key=f"ping-notify:{ping.id}:{recipient.id}"
        )
        await sms_outbox_service.record_send_result(
            db,
            to_phone_number=recipient.phone_number,
            purpose=SmsOutboxPurpose.ping_notification,
            body=message,
            result=result,
            related_ping_id=ping.id,
        )
