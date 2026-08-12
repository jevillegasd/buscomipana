import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.gateways.base import MAX_SMS_SEGMENT_CHARS
from app.models.sms import SmsOutboxEntry
from app.services import auth_service
from tests.conftest import signup_and_login

PHONE_SUBJECT = "+573005550001"
PHONE_RELATIVE = "+573005550002"
PHONE_RESPONDER = "+573005550003"
PHONE_ADMIN = "+573005550004"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


async def _accept_relative_link(client, *, requester, target_phone, target):
    resp = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": target_phone, "relationship_label": "sibling"},
        headers=auth_headers(requester),
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"/api/v1/relative-links/{resp.json()['id']}/accept", headers=auth_headers(target)
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_ok_ping_does_not_fan_out_but_distress_does(client, db_engine):
    subject = await signup_and_login(client, PHONE_SUBJECT)
    relative = await signup_and_login(client, PHONE_RELATIVE)
    await _accept_relative_link(client, requester=relative, target_phone=PHONE_SUBJECT, target=subject)

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def outbox_count(purpose="ping_notification"):
        async with session_factory() as db:
            result = await db.execute(select(SmsOutboxEntry).where(SmsOutboxEntry.purpose == purpose))
            return len(result.scalars().all())

    assert await outbox_count() == 0

    resp = await client.post("/api/v1/pings", json={"status": "ok"}, headers=auth_headers(subject))
    assert resp.status_code == 201, resp.text
    assert await outbox_count() == 0, "an OK ping must not trigger any SMS fanout"

    resp = await client.post("/api/v1/pings", json={"status": "distress"}, headers=auth_headers(subject))
    assert resp.status_code == 201, resp.text
    assert await outbox_count() == 1, "a distress ping must notify the accepted relative"


@pytest.mark.asyncio
async def test_verified_responders_are_never_sms_notified(client, db_engine, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "admin_phone_numbers", PHONE_ADMIN)

    admin = await signup_and_login(client, PHONE_ADMIN)
    subject = await signup_and_login(client, PHONE_SUBJECT)
    responder = await signup_and_login(client, PHONE_RESPONDER)

    resp = await client.post(
        "/api/v1/responders/apply",
        json={"organization_name": "Cruz Roja", "credential_type": "red_cross"},
        headers=auth_headers(responder),
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"/api/v1/admin/responders/{responder['user_id']}/verify", headers=auth_headers(admin)
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post("/api/v1/pings", json={"status": "distress"}, headers=auth_headers(subject))
    assert resp.status_code == 201, resp.text

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(
            select(SmsOutboxEntry).where(SmsOutboxEntry.purpose == "ping_notification")
        )
        entries = result.scalars().all()
        assert entries == [], "verified responders should not receive an SMS fanout (deferred to their own frontend)"


@pytest.mark.asyncio
async def test_distress_message_is_included_and_stays_within_one_sms_segment(client, db_engine):
    subject = await signup_and_login(client, PHONE_SUBJECT)
    relative = await signup_and_login(client, PHONE_RELATIVE)
    await _accept_relative_link(client, requester=relative, target_phone=PHONE_SUBJECT, target=subject)

    resp = await client.post(
        "/api/v1/pings",
        json={"status": "distress", "message": "Atrapado en el carro, sin señal, envíen ayuda ya"},
        headers=auth_headers(subject),
    )
    assert resp.status_code == 201, resp.text

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(select(SmsOutboxEntry).where(SmsOutboxEntry.purpose == "ping_notification"))
        entry = result.scalars().one()
        assert "NECESITA AYUDA" in entry.body
        assert "Atrapado en el carro" in entry.body
        assert len(entry.body) <= MAX_SMS_SEGMENT_CHARS
        # í has no GSM-7 representation -- "señal" (ñ is GSM-7-safe) stays as-is
        # but "envíen" must lose its accent.
        assert "envien" in entry.body
        assert "señal" in entry.body


@pytest.mark.asyncio
async def test_very_long_distress_message_is_clipped_without_losing_the_status_line(client, db_engine):
    subject = await signup_and_login(client, PHONE_SUBJECT)
    relative = await signup_and_login(client, PHONE_RELATIVE)
    await _accept_relative_link(client, requester=relative, target_phone=PHONE_SUBJECT, target=subject)

    resp = await client.post(
        "/api/v1/pings",
        json={"status": "distress", "message": "x" * 400},
        headers=auth_headers(subject),
    )
    assert resp.status_code == 201, resp.text

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(select(SmsOutboxEntry).where(SmsOutboxEntry.purpose == "ping_notification"))
        entry = result.scalars().one()
        assert len(entry.body) == MAX_SMS_SEGMENT_CHARS
        assert "NECESITA AYUDA" in entry.body
