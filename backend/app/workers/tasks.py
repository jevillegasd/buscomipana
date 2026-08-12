import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import async_session_factory
from app.gateways.factory import get_gateway
from app.models.enums import SmsOutboxPurpose, SmsOutboxStatus
from app.models.sms import SmsOutboxEntry
from app.workers.celery_app import celery_app

MAX_SMS_ATTEMPTS = 5


def _run(coro):
    # Each task invocation gets its own event loop. Safe because Celery task
    # bodies run in a worker process/thread with no pre-existing running loop --
    # unlike the FastAPI request path, which awaits the async services directly
    # instead of going through Celery, precisely to avoid that conflict.
    return asyncio.run(coro)


@celery_app.task(name="send_queued_sms")
def send_queued_sms(outbox_id: str) -> None:
    _run(_send_queued_sms(outbox_id))


async def _send_queued_sms(outbox_id: str) -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(SmsOutboxEntry).where(SmsOutboxEntry.id == uuid.UUID(outbox_id)))
        entry = result.scalar_one_or_none()
        if entry is None or entry.status == SmsOutboxStatus.delivered:
            return

        gateway = get_gateway()
        send_result = await gateway.send_sms(entry.to_phone_number, entry.body, idempotency_key=f"outbox:{entry.id}")
        entry.attempt_count += 1
        if send_result.accepted:
            entry.status = SmsOutboxStatus.sent
            entry.provider_message_id = send_result.provider_message_id
            entry.last_error = None
        else:
            entry.status = SmsOutboxStatus.failed
            entry.last_error = send_result.error
        await db.commit()


@celery_app.task(name="retry_failed_sms")
def retry_failed_sms() -> int:
    return _run(_retry_failed_sms())


async def _retry_failed_sms() -> int:
    async with async_session_factory() as db:
        result = await db.execute(
            select(SmsOutboxEntry).where(
                SmsOutboxEntry.status == SmsOutboxStatus.failed,
                SmsOutboxEntry.attempt_count < MAX_SMS_ATTEMPTS,
                # OTP entries are excluded: send_queued_sms retries by
                # resending entry.body verbatim through the generic SMS API,
                # which is actively wrong for a provider-managed OTP (see
                # NotificationGateway.verifies_otp_externally) -- entry.body
                # there is just a placeholder, not the code the user needs.
                # Even for a locally-generated code, resending a stale one
                # minutes later isn't useful -- the user already has their
                # own "Reenviar codigo" button to request a fresh one.
                SmsOutboxEntry.purpose != SmsOutboxPurpose.otp,
            )
        )
        entries = result.scalars().all()
        for entry in entries:
            send_queued_sms.delay(str(entry.id))
        return len(entries)


@celery_app.task(name="cleanup_expired_otps")
def cleanup_expired_otps() -> int:
    return _run(_cleanup_expired_otps())


async def _cleanup_expired_otps() -> int:
    from app.models.otp import OtpVerification

    cutoff = datetime.now(UTC) - timedelta(days=1)
    async with async_session_factory() as db:
        result = await db.execute(select(OtpVerification).where(OtpVerification.expires_at < cutoff))
        stale = result.scalars().all()
        for otp in stale:
            await db.delete(otp)
        await db.commit()
        return len(stale)


@celery_app.task(name="anonymize_ping")
def anonymize_ping(ping_id: str) -> None:
    _run(_anonymize_ping(ping_id))


async def _anonymize_ping(ping_id: str) -> None:
    from app.models.ping import Ping
    from app.services import analytics_service

    async with async_session_factory() as db:
        result = await db.execute(select(Ping).where(Ping.id == uuid.UUID(ping_id)))
        ping = result.scalar_one_or_none()
        if ping is None:
            return
        await analytics_service.anonymize_ping(db, ping=ping)
        await db.commit()


@celery_app.task(name="record_pong_latency")
def record_pong_latency(pong_id: str) -> None:
    _run(_record_pong_latency(pong_id))


async def _record_pong_latency(pong_id: str) -> None:
    from app.models.ping import Ping, Pong
    from app.services import analytics_service

    async with async_session_factory() as db:
        result = await db.execute(select(Pong).where(Pong.id == uuid.UUID(pong_id)))
        pong = result.scalar_one_or_none()
        if pong is None:
            return
        ping_result = await db.execute(select(Ping).where(Ping.id == pong.ping_id))
        ping = ping_result.scalar_one_or_none()
        if ping is None:
            return
        await analytics_service.record_pong_latency(db, ping=ping, pong_created_at=pong.created_at)
        await db.commit()


@celery_app.task(name="search_missing_person_candidates")
def search_missing_person_candidates(report_id: str) -> int:
    return _run(_search_missing_person_candidates(report_id))


async def _search_missing_person_candidates(report_id: str) -> int:
    from app.services import matching_service, missing_person_report_service

    async with async_session_factory() as db:
        report = await missing_person_report_service.get_report(db, report_id=uuid.UUID(report_id))
        candidates = await matching_service.populate_candidates(db, report=report)
        await db.commit()
        return len(candidates)
