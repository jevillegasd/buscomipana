from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.gateways.mock_gateway import get_last_sent_message
from app.models.otp import OtpVerification
from app.services import auth_service

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
