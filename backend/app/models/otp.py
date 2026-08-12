import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Channel, OtpPurpose
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.types import str_enum


class OtpVerification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "otp_verifications"
    __table_args__ = (Index("ix_otp_phone_purpose_expires", "phone_number", "purpose", "expires_at"),)

    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    purpose: Mapped[OtpPurpose] = mapped_column(str_enum(OtpPurpose, 32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[Channel] = mapped_column(str_enum(Channel, 20), nullable=False, default=Channel.sms)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    device_label: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrustedDevice(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A "remember this browser" grant, minted on logout (see auth_service.
    remember_device). Scoped to a specific phone number, not just a user, so a
    stale cookie never skips OTP for a *different* number that later logs in
    from the same browser."""

    __tablename__ = "trusted_devices"
    __table_args__ = (Index("ix_trusted_devices_phone", "phone_number"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PhoneNumberChange(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "phone_number_changes"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    old_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    new_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_via_otp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("otp_verifications.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
