import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.enums import SmsOutboxPurpose, SmsOutboxStatus
from app.models.sms import SmsOutboxEntry
from app.workers import tasks as tasks_module


def test_send_queued_sms_marks_sent_via_mock_gateway(monkeypatch):
    # Exercises the Celery task's async implementation directly against an
    # isolated in-memory SQLite DB -- avoids nesting asyncio.run() inside an
    # already-running event loop, which is the real reason the FastAPI request
    # path awaits notification_service/auth_service directly instead of calling
    # these tasks synchronously; real deployments enqueue them via .delay()
    # from a separate Celery worker process instead.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[SmsOutboxEntry.__table__])

        async with session_factory() as db:
            entry = SmsOutboxEntry(
                to_phone_number="+573009999999",
                purpose=SmsOutboxPurpose.otp,
                body="Your Buscomipana code is 123456",
                status=SmsOutboxStatus.queued,
            )
            db.add(entry)
            await db.commit()
            entry_id = entry.id

        monkeypatch.setattr(tasks_module, "async_session_factory", session_factory)
        await tasks_module._send_queued_sms(str(entry_id))

        async with session_factory() as db:
            refreshed = await db.get(SmsOutboxEntry, entry_id)
            assert refreshed.status == SmsOutboxStatus.sent
            assert refreshed.attempt_count == 1
            assert refreshed.provider_message_id

        await engine.dispose()

    asyncio.run(scenario())


def test_retry_failed_sms_requeues_only_failed_under_max_attempts(monkeypatch):
    # Purpose here is deliberately ping_notification, not otp -- OTP entries
    # are excluded from this sweep entirely (see _retry_failed_sms), so using
    # SmsOutboxPurpose.otp fixtures would make every case here vanish from
    # the query regardless of status/attempt_count, and the test would not
    # actually exercise the filtering logic it's named for.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[SmsOutboxEntry.__table__])

        async with session_factory() as db:
            db.add_all(
                [
                    SmsOutboxEntry(
                        to_phone_number="+573001111111",
                        purpose=SmsOutboxPurpose.ping_notification,
                        body="retryable",
                        status=SmsOutboxStatus.failed,
                        attempt_count=1,
                    ),
                    SmsOutboxEntry(
                        to_phone_number="+573002222222",
                        purpose=SmsOutboxPurpose.ping_notification,
                        body="exhausted",
                        status=SmsOutboxStatus.failed,
                        attempt_count=tasks_module.MAX_SMS_ATTEMPTS,
                    ),
                    SmsOutboxEntry(
                        to_phone_number="+573003333333",
                        purpose=SmsOutboxPurpose.ping_notification,
                        body="already sent",
                        status=SmsOutboxStatus.sent,
                        attempt_count=1,
                    ),
                ]
            )
            await db.commit()

        monkeypatch.setattr(tasks_module, "async_session_factory", session_factory)
        requeued_ids = []
        monkeypatch.setattr(
            tasks_module.send_queued_sms, "delay", lambda outbox_id: requeued_ids.append(outbox_id)
        )

        count = await tasks_module._retry_failed_sms()

        assert count == 1
        assert len(requeued_ids) == 1

        await engine.dispose()

    asyncio.run(scenario())
