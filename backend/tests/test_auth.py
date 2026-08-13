from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.gateways.mock_gateway import get_last_sent_message
from app.models.enums import Channel
from app.models.otp import OtpVerification
from app.services import auth_service, email_service

PHONE = "+573001234567"


async def _request_and_verify(client, phone_number: str) -> dict:
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_number})
    assert resp.status_code == 202, resp.text
    message = get_last_sent_message(phone_number)
    code = "".join(ch for ch in message if ch.isdigit())[-6:]
    resp = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone_number, "code": code})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_otp_signup_login_round_trip(client, monkeypatch):
    # This test fires several OTP requests back-to-back for the same number to
    # exercise repeat-login / wrong-code flows -- that's a different concern
    # from the resend cooldown (covered separately below), so disable it here.
    monkeypatch.setattr(auth_service.settings, "otp_resend_cooldown_seconds", 0)

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": PHONE})
    assert resp.status_code == 202

    message = get_last_sent_message(PHONE)
    assert message is not None
    code = "".join(ch for ch in message if ch.isdigit())[-6:]

    resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_number": PHONE, "code": code}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_new_account"] is True
    access_token = body["access_token"]
    refresh_token = body["refresh_token"]

    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone_number"] == PHONE

    # second login (same phone) should not create a new account
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": PHONE})
    assert resp.status_code == 202
    message = get_last_sent_message(PHONE)
    code = "".join(ch for ch in message if ch.isdigit())[-6:]
    resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_number": PHONE, "code": code}
    )
    assert resp.status_code == 200
    assert resp.json()["is_new_account"] is False

    # wrong code is rejected
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": PHONE})
    assert resp.status_code == 202
    resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_number": PHONE, "code": "000000"}
    )
    assert resp.status_code == 400

    # refresh rotates the token
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != refresh_token

    # old refresh token is now revoked
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_otp_resend_cooldown_blocks_then_allows_after_window(client, db_engine):
    phone = "+573001234598"

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202
    assert resp.json()["resend_cooldown_seconds"] == 60

    # Immediately retrying for the same number is blocked.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["retry_after_seconds"] > 0

    # Backdate the OTP row past the cooldown window -- the same request that
    # was just blocked should now go through.
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(select(OtpVerification).where(OtpVerification.phone_number == phone))
        otp = result.scalars().one()
        otp.created_at = datetime.now(UTC) - timedelta(seconds=61)
        await db.commit()

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_logout_then_login_same_browser_skips_otp(client):
    phone = "+573001234597"
    await _request_and_verify(client, phone)

    # Logging out mints a 10-day "remember this browser" cookie.
    resp = await client.post("/api/v1/auth/logout", json={})
    assert resp.status_code == 204
    assert "bmp_remember_device" in resp.cookies

    # Requesting a new OTP for the SAME number from the same browser (same
    # cookie jar) skips sending a code entirely and logs the user back in.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202
    assert resp.json()["skipped_otp"] is True

    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone_number"] == phone


@pytest.mark.asyncio
async def test_remembered_device_does_not_skip_otp_for_a_different_number(client):
    phone_a = "+573001234596"
    phone_b = "+573001234595"
    await _request_and_verify(client, phone_a)

    resp = await client.post("/api/v1/auth/logout", json={})
    assert resp.status_code == 204

    # Same browser, different phone number -- must not skip the OTP.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_b})
    assert resp.status_code == 202
    assert resp.json()["skipped_otp"] is False


@pytest.mark.asyncio
async def test_otp_request_rejects_unsupported_country(client):
    # Only Colombia (+57) and the UAE (+971) are supported right now -- any
    # other calling code should be rejected before an OTP is ever sent.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": "+14155552671"})
    assert resp.status_code == 422, resp.text
    assert get_last_sent_message("+14155552671") is None


@pytest.mark.asyncio
async def test_otp_request_allows_uae_numbers(client):
    phone = "+971501234567"
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202, resp.text


@pytest.mark.asyncio
async def test_logout_all_revokes_remembered_device_too(client, monkeypatch):
    # Calls otp/request twice for the same number (once up front, once at the
    # end to confirm it's no longer skipped) -- disable the unrelated resend
    # cooldown so only the trusted-device revocation is under test here.
    monkeypatch.setattr(auth_service.settings, "otp_resend_cooldown_seconds", 0)

    phone = "+573001234594"
    body = await _request_and_verify(client, phone)

    resp = await client.post("/api/v1/auth/logout", json={})
    assert resp.status_code == 204
    assert "bmp_remember_device" in resp.cookies

    # logout-all is the "I lost my phone" panic button -- it should also kill
    # any remembered browser, not just active sessions.
    resp = await client.post(
        "/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert resp.status_code == 204

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202
    assert resp.json()["skipped_otp"] is False


@pytest.mark.asyncio
async def test_otp_request_with_email_sends_via_email_not_sms(client, monkeypatch, db_engine):
    # Falls back to email delivery when SMS is unreliable/blocked for this
    # number's carrier -- the account is still identified by phone_number
    # (see auth_service.request_login_otp), only the delivery channel changes.
    sent = []

    async def fake_send_otp_email(to_address: str, code: str) -> bool:
        sent.append((to_address, code))
        return True

    monkeypatch.setattr(email_service, "send_otp_email", fake_send_otp_email)

    phone = "+573009998801"
    resp = await client.post(
        "/api/v1/auth/otp/request", json={"phone_number": phone, "email": "test@example.com"}
    )
    assert resp.status_code == 202, resp.text

    # Nothing went out over the SMS gateway for this number.
    assert get_last_sent_message(phone) is None
    assert len(sent) == 1
    assert sent[0][0] == "test@example.com"
    code = sent[0][1]

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(select(OtpVerification).where(OtpVerification.phone_number == phone))
        otp = result.scalar_one()
        assert otp.channel == Channel.email

    resp = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "code": code})
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_otp_request_email_send_failure_is_recorded_but_still_returns_202(client, monkeypatch):
    async def failing_send_otp_email(to_address: str, code: str) -> bool:
        return False

    monkeypatch.setattr(email_service, "send_otp_email", failing_send_otp_email)

    phone = "+573009998802"
    resp = await client.post(
        "/api/v1/auth/otp/request", json={"phone_number": phone, "email": "test@example.com"}
    )
    # Same as a failed SMS send (see _create_and_send_otp) -- the failure is
    # recorded in the outbox for visibility, not surfaced as a request error,
    # since the caller has already been told a code is "on its way".
    assert resp.status_code == 202, resp.text
