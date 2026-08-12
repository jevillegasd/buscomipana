import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.countries import is_allowed_phone_number
from app.core.security import (
    create_access_token,
    ensure_aware,
    generate_opaque_token,
    generate_otp_code,
    hash_otp_code,
    hash_token,
    refresh_token_expiry,
    verify_otp_code,
)
from app.gateways.base import render_otp_message
from app.gateways.factory import get_gateway
from app.models.enums import Channel, OtpPurpose, PingStatus, SmsOutboxPurpose, UserRole
from app.models.otp import (
    AuthSession,
    OtpVerification,
    PhoneNumberChange,
    TrustedDevice,
)
from app.models.user import User
from app.services import (
    missing_person_report_service,
    ping_service,
    relative_link_service,
    sms_outbox_service,
)

settings = get_settings()


class OtpError(Exception):
    pass


class InvalidOrExpiredOtp(OtpError):
    pass


class TooManyOtpAttempts(OtpError):
    pass


class PhoneNumberTaken(OtpError):
    pass


class UnsupportedCountry(OtpError):
    pass


class OtpCooldownActive(OtpError):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"OTP resend cooldown active, retry after {retry_after_seconds}s")


async def _create_and_send_otp(
    db: AsyncSession, *, phone_number: str, purpose: OtpPurpose, user_id: uuid.UUID | None
) -> OtpVerification:
    last_result = await db.execute(
        select(OtpVerification)
        .where(OtpVerification.phone_number == phone_number, OtpVerification.purpose == purpose)
        .order_by(OtpVerification.created_at.desc())
        .limit(1)
    )
    last = last_result.scalar_one_or_none()
    if last is not None:
        cooldown = timedelta(seconds=settings.otp_resend_cooldown_seconds)
        elapsed = datetime.now(UTC) - ensure_aware(last.created_at)
        if elapsed < cooldown:
            raise OtpCooldownActive(retry_after_seconds=int((cooldown - elapsed).total_seconds()) + 1)

    code = generate_otp_code()
    otp = OtpVerification(
        phone_number=phone_number,
        user_id=user_id,
        purpose=purpose,
        code_hash=hash_otp_code(code),
        channel="sms",
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.otp_ttl_minutes),
    )
    db.add(otp)
    await db.flush()

    gateway = get_gateway()
    result = await gateway.send_otp(phone_number, code)
    await sms_outbox_service.record_send_result(
        db,
        to_phone_number=phone_number,
        purpose=SmsOutboxPurpose.otp,
        body=render_otp_message(code),
        result=result,
        related_otp_id=otp.id,
    )

    return otp


async def request_login_otp(db: AsyncSession, phone_number: str) -> OtpVerification:
    # Checked before sending anything -- an unsupported-country number should
    # never cost SMS spend, and shouldn't be able to probe whether an account
    # exists there either.
    if not is_allowed_phone_number(phone_number):
        raise UnsupportedCountry(phone_number)
    return await _create_and_send_otp(
        db, phone_number=phone_number, purpose=OtpPurpose.signup_or_login, user_id=None
    )


async def request_phone_change_otp(db: AsyncSession, *, user: User, new_phone_number: str) -> OtpVerification:
    existing = await db.execute(
        select(User).where(User.phone_number == new_phone_number, User.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none() is not None:
        raise PhoneNumberTaken(new_phone_number)
    return await _create_and_send_otp(
        db, phone_number=new_phone_number, purpose=OtpPurpose.phone_change, user_id=user.id
    )


async def _consume_otp(
    db: AsyncSession, *, phone_number: str, code: str, purpose: OtpPurpose
) -> OtpVerification:
    result = await db.execute(
        select(OtpVerification)
        .where(
            OtpVerification.phone_number == phone_number,
            OtpVerification.purpose == purpose,
            OtpVerification.consumed_at.is_(None),
        )
        .order_by(OtpVerification.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()
    if otp is None:
        raise InvalidOrExpiredOtp()

    now = datetime.now(UTC)
    if ensure_aware(otp.expires_at) < now:
        raise InvalidOrExpiredOtp()
    if otp.attempt_count >= settings.otp_max_attempts:
        raise TooManyOtpAttempts()

    otp.attempt_count += 1
    if not verify_otp_code(code, otp.code_hash):
        await db.flush()
        raise InvalidOrExpiredOtp()

    otp.consumed_at = now
    await db.flush()
    return otp


async def verify_login_otp(db: AsyncSession, *, phone_number: str, code: str) -> tuple[User, bool]:
    await _consume_otp(db, phone_number=phone_number, code=code, purpose=OtpPurpose.signup_or_login)

    result = await db.execute(select(User).where(User.phone_number == phone_number, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    is_new_account = user is None
    if user is None:
        # Bootstrap mechanism: there's no signup flow for admins (no passwords,
        # no invite system yet), so a phone number listed in ADMIN_PHONE_NUMBERS
        # is promoted to admin the moment it first signs up.
        role = UserRole.admin if phone_number in settings.admin_phone_number_list else UserRole.user
        user = User(phone_number=phone_number, role=role)
        db.add(user)
        await db.flush()

        # Every new account starts with an initial "OK" self-ping -- gives the
        # account a first entry in its ping history, and gives distant relatives
        # who already reported this phone number missing something to match
        # against (see resolve_open_reports_for_new_user below).
        await ping_service.create_ping(
            db,
            reported_by_user_id=user.id,
            subject_user_id=None,
            status=PingStatus.ok,
            message=None,
            latitude=None,
            longitude=None,
            location_accuracy_m=None,
            channel=Channel.web,
        )

        # Mirror of the exact-match check in missing_person_report_service.
        # create_report(): a report may have been filed against this phone
        # number *before* this person ever had an account ("unclaimed" subject).
        # Resolve and notify those reporters now that the account exists.
        await missing_person_report_service.resolve_open_reports_for_new_user(db, new_user=user)

        # Same "unclaimed" pattern for relative-link requests filed against
        # this phone number before it ever had an account -- see
        # relative_link_service.request_link.
        await relative_link_service.resolve_open_links_for_new_user(db, new_user=user)
    else:
        user.last_login_at = datetime.now(UTC)

    return user, is_new_account


async def confirm_phone_change(db: AsyncSession, *, user: User, new_phone_number: str, code: str) -> User:
    otp = await _consume_otp(db, phone_number=new_phone_number, code=code, purpose=OtpPurpose.phone_change)

    old_phone_number = user.phone_number
    user.phone_number = new_phone_number
    db.add(
        PhoneNumberChange(
            user_id=user.id,
            old_phone_number=old_phone_number,
            new_phone_number=new_phone_number,
            verified_via_otp_id=otp.id,
            changed_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return user


async def create_session(db: AsyncSession, *, user: User, device_label: str | None = None) -> tuple[str, str]:
    refresh_token = generate_opaque_token()
    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        device_label=device_label,
        expires_at=refresh_token_expiry(),
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(user_id=str(user.id), role=user.role.value)
    return access_token, refresh_token


async def rotate_session(db: AsyncSession, *, refresh_token: str) -> tuple[str, str] | None:
    token_hash = hash_token(refresh_token)
    result = await db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if (
        session is None
        or session.revoked_at is not None
        or ensure_aware(session.expires_at) < datetime.now(UTC)
    ):
        return None

    session.revoked_at = datetime.now(UTC)

    user_result = await db.execute(select(User).where(User.id == session.user_id, User.deleted_at.is_(None)))
    user = user_result.scalar_one_or_none()
    if user is None:
        return None

    return await create_session(db, user=user, device_label=session.device_label)


async def revoke_session(db: AsyncSession, *, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    await db.execute(
        update(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    # "Log out everywhere" should also stop skipping OTP on any remembered
    # browser -- otherwise a stale trusted-device cookie would let someone
    # back in without a code even after the user deliberately kicked every
    # session out (e.g. lost phone).
    await revoke_trusted_devices(db, user_id=user_id)


async def remember_device(db: AsyncSession, *, user: User) -> str:
    """Mints an opaque, hashed token pairing this browser with the user's
    current phone number for settings.remember_device_ttl_days. Called from
    the /auth/logout route so the *next* login from the same browser for the
    same number can skip sending/verifying an OTP (see try_device_login)."""
    raw_token = generate_opaque_token()
    db.add(
        TrustedDevice(
            user_id=user.id,
            phone_number=user.phone_number,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.remember_device_ttl_days),
        )
    )
    await db.flush()
    return raw_token


async def try_device_login(db: AsyncSession, *, phone_number: str, device_token: str | None) -> User | None:
    """Returns the user to log in as if device_token is a live, unexpired
    trusted-device grant for exactly this phone number -- None otherwise
    (missing cookie, expired/revoked grant, or a different number), in which
    case the caller should fall back to sending a real OTP."""
    if not device_token:
        return None

    result = await db.execute(select(TrustedDevice).where(TrustedDevice.token_hash == hash_token(device_token)))
    device = result.scalar_one_or_none()
    if device is None or device.revoked_at is not None or ensure_aware(device.expires_at) < datetime.now(UTC):
        return None
    if device.phone_number != phone_number:
        return None

    user_result = await db.execute(select(User).where(User.id == device.user_id, User.deleted_at.is_(None)))
    return user_result.scalar_one_or_none()


async def revoke_trusted_devices(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await db.execute(
        update(TrustedDevice)
        .where(TrustedDevice.user_id == user_id, TrustedDevice.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def logout_and_remember_device(db: AsyncSession, *, refresh_token: str) -> str | None:
    """Revokes the session behind refresh_token and, if it maps to a live
    session/user, mints a fresh trusted-device token for them (see
    remember_device). Returns the raw token to set as a cookie, or None if
    the refresh token didn't identify a session (nothing to remember)."""
    token_hash = hash_token(refresh_token)
    result = await db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is None:
        return None

    session.revoked_at = datetime.now(UTC)

    user_result = await db.execute(select(User).where(User.id == session.user_id, User.deleted_at.is_(None)))
    user = user_result.scalar_one_or_none()
    if user is None:
        return None

    return await remember_device(db, user=user)
