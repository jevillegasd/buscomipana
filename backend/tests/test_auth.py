from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.gateways.mock_gateway import get_last_sent_message
from app.models.enums import Channel
from app.models.otp import OtpVerification
from app.models.user import User
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


async def _give_user_a_verified_email(client, monkeypatch, *, access_token: str, email: str) -> None:
    """A user can only ever get a verified email through this authenticated
    request/confirm round-trip (Issue #10) -- there's no shortcut, by design,
    so every test that needs one goes through the real flow."""
    sent = {}

    async def fake_send_otp_email(to_address: str, code: str) -> bool:
        sent["to"] = to_address
        sent["code"] = code
        return True

    monkeypatch.setattr(email_service, "send_otp_email", fake_send_otp_email)

    resp = await client.post(
        "/api/v1/auth/email/request",
        json={"new_email": email},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 202, resp.text
    assert sent["to"] == email

    resp = await client.post(
        "/api/v1/auth/email/confirm",
        json={"new_email": email, "code": sent["code"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200, resp.text


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
async def test_otp_request_use_email_sends_to_stored_email_not_sms(client, monkeypatch, db_engine):
    phone = "+573009998801"
    signup = await _request_and_verify(client, phone)
    await _give_user_a_verified_email(
        client, monkeypatch, access_token=signup["access_token"], email="real@example.com"
    )

    sent = {}

    async def fake_send_otp_email(to_address: str, code: str) -> bool:
        sent["to"] = to_address
        sent["code"] = code
        return True

    monkeypatch.setattr(email_service, "send_otp_email", fake_send_otp_email)
    monkeypatch.setattr(auth_service.settings, "otp_resend_cooldown_seconds", 0)

    # Signup (via _request_and_verify) already left a message in the SMS mock
    # -- capture it so we can confirm the email-channel request below doesn't
    # add a *new* one, rather than wrongly expecting None (which ignores that
    # earlier legitimate SMS send).
    message_before = get_last_sent_message(phone)

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone, "use_email": True})
    assert resp.status_code == 202, resp.text
    assert resp.json()["email_hint"] == "r**l@example.com"

    # No new SMS went out for this login round -- the mock's last-sent-message
    # is unchanged from before the email-channel request.
    assert get_last_sent_message(phone) == message_before
    assert sent["to"] == "real@example.com"

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            select(OtpVerification)
            .where(OtpVerification.phone_number == phone, OtpVerification.purpose == "signup_or_login")
            .order_by(OtpVerification.created_at.desc())
        )
        otp = result.scalars().first()
        assert otp.channel == Channel.email

    resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_number": phone, "code": sent["code"]}
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_otp_request_use_email_rejected_when_no_verified_email_on_file(client):
    # Issue #10 regression: this used to be exactly the account-takeover
    # hole -- an unauthenticated caller could supply *any* email for *any*
    # phone_number (including one they don't own) and receive that number's
    # OTP themselves. Now use_email only ever delivers to a stored, already-
    # verified email -- a phone number with none on file must be rejected,
    # not silently fall back to anything client-controlled.
    victim_phone = "+573009998805"
    resp = await client.post(
        "/api/v1/auth/otp/request", json={"phone_number": victim_phone, "use_email": True}
    )
    assert resp.status_code == 409, resp.text
    assert get_last_sent_message(victim_phone) is None


@pytest.mark.asyncio
async def test_otp_request_email_send_failure_is_recorded_but_still_returns_202(client, monkeypatch):
    phone = "+573009998802"
    signup = await _request_and_verify(client, phone)
    await _give_user_a_verified_email(
        client, monkeypatch, access_token=signup["access_token"], email="real2@example.com"
    )

    async def failing_send_otp_email(to_address: str, code: str) -> bool:
        return False

    monkeypatch.setattr(email_service, "send_otp_email", failing_send_otp_email)
    monkeypatch.setattr(auth_service.settings, "otp_resend_cooldown_seconds", 0)

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone, "use_email": True})
    # Same as a failed SMS send (see _create_and_send_otp) -- the failure is
    # recorded in the outbox for visibility, not surfaced as a request error,
    # since the caller has already been told a code is "on its way".
    assert resp.status_code == 202, resp.text


@pytest.mark.asyncio
async def test_first_switch_to_email_skips_cooldown_but_second_email_send_does_not(
    client, monkeypatch, db_engine
):
    phone = "+573009998803"
    signup = await _request_and_verify(client, phone)
    await _give_user_a_verified_email(
        client, monkeypatch, access_token=signup["access_token"], email="real3@example.com"
    )

    async def fake_send_otp_email(to_address: str, code: str) -> bool:
        return True

    monkeypatch.setattr(email_service, "send_otp_email", fake_send_otp_email)

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    # _request_and_verify's own signup SMS already started a cooldown
    # moments ago -- expire it so the "SMS just went out" send below is a
    # clean, fresh one rather than itself getting blocked by leftover state.
    async with session_factory() as db:
        result = await db.execute(
            select(OtpVerification)
            .where(OtpVerification.phone_number == phone, OtpVerification.purpose == "signup_or_login")
            .order_by(OtpVerification.created_at.desc())
        )
        signup_otp = result.scalars().first()
        signup_otp.created_at = datetime.now(UTC) - timedelta(seconds=120)
        await db.commit()

    # SMS just went out -- normally this starts a 60s cooldown on any resend.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202, resp.text

    # Backdate it a couple seconds -- SQLite's server-side now() (used in unit
    # tests; Postgres has real microsecond resolution in production) only
    # has 1-second resolution, so two rows inserted in the same test can tie
    # on created_at and make "the last row" ambiguous. Not needed for this
    # assertion (the cooldown bypass ignores timing entirely) but needed so
    # the *next* step reliably sees this SMS row as strictly older.
    async with session_factory() as db:
        result = await db.execute(
            select(OtpVerification)
            .where(OtpVerification.phone_number == phone, OtpVerification.purpose == "signup_or_login")
            .order_by(OtpVerification.created_at.desc())
        )
        sms_otp = result.scalars().first()
        sms_otp.created_at = datetime.now(UTC) - timedelta(seconds=5)
        await db.commit()

    # Switching to email right away is NOT blocked by that cooldown -- the
    # email fallback exists specifically for "SMS isn't arriving," so making
    # someone wait it out first would defeat the point.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone, "use_email": True})
    assert resp.status_code == 202, resp.text

    # But the email send itself restarts the cooldown -- a second email
    # attempt right after is blocked same as any other resend.
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone, "use_email": True})
    assert resp.status_code == 429, resp.text


@pytest.mark.asyncio
async def test_new_account_gets_phone_verified_on_real_sms_login(client, db_engine):
    phone = "+573009998806"
    await _request_and_verify(client, phone)

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(select(User).where(User.phone_number == phone))
        user = result.scalar_one()
        assert user.phone_verified_at is not None


@pytest.mark.asyncio
async def test_legacy_unverified_account_becomes_verified_after_real_sms_login(client, db_engine, monkeypatch):
    # Simulates an account that predates Issue #10's fix -- could only have
    # been created through the vulnerable email-any-address path, so
    # phone_verified_at is NULL. A real SMS login (the only login path left
    # for it, since request_login_otp refuses email without an already-
    # verified one) should retroactively mark it verified.
    monkeypatch.setattr(auth_service.settings, "otp_resend_cooldown_seconds", 0)
    phone = "+573009998807"
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(User(phone_number=phone, phone_verified_at=None))
        await db.commit()

    await _request_and_verify(client, phone)

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.phone_number == phone))
        user = result.scalar_one()
        assert user.phone_verified_at is not None


@pytest.mark.asyncio
async def test_request_email_change_requires_phone_verified(client, db_engine):
    # Defense in depth (see auth_service.PhoneNotVerified's docstring): an
    # account that's never proven it controls its own phone shouldn't be
    # able to entrench further by attaching an email.
    phone = "+573009998808"
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        user = User(phone_number=phone, phone_verified_at=None)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    from app.core.security import create_access_token

    token = create_access_token(user_id=str(user.id), role="user")
    resp = await client.post(
        "/api/v1/auth/email/request",
        json={"new_email": "shouldnotwork@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_confirm_email_change_rejects_code_for_a_different_email(client, monkeypatch):
    # Regression test for a bypass caught during review: the code alone
    # isn't proof, it must also be the one actually sent to *this* address --
    # otherwise an authenticated caller could request a code to their own
    # inbox and reuse it to confirm a completely different address they've
    # never proven they control.
    phone = "+573009998809"
    signup = await _request_and_verify(client, phone)

    sent = {}

    async def fake_send_otp_email(to_address: str, code: str) -> bool:
        sent["to"] = to_address
        sent["code"] = code
        return True

    monkeypatch.setattr(email_service, "send_otp_email", fake_send_otp_email)

    resp = await client.post(
        "/api/v1/auth/email/request",
        json={"new_email": "mine@example.com"},
        headers={"Authorization": f"Bearer {signup['access_token']}"},
    )
    assert resp.status_code == 202, resp.text

    resp = await client.post(
        "/api/v1/auth/email/confirm",
        json={"new_email": "someone-elses@example.com", "code": sent["code"]},
        headers={"Authorization": f"Bearer {signup['access_token']}"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_email_taken_by_another_active_user_is_rejected(client, monkeypatch):
    phone_a = "+573009998810"
    phone_b = "+573009998811"
    signup_a = await _request_and_verify(client, phone_a)
    signup_b = await _request_and_verify(client, phone_b)

    await _give_user_a_verified_email(
        client, monkeypatch, access_token=signup_a["access_token"], email="shared@example.com"
    )

    resp = await client.post(
        "/api/v1/auth/email/request",
        json={"new_email": "shared@example.com"},
        headers={"Authorization": f"Bearer {signup_b['access_token']}"},
    )
    assert resp.status_code == 409, resp.text
