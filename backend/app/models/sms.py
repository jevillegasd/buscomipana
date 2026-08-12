import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import SmsIntent, SmsOutboxPurpose, SmsOutboxStatus
from app.models.mixins import UUIDPrimaryKeyMixin
from app.models.types import PortableJSON, str_enum


class InboundSmsMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "inbound_sms_messages"

    provider_message_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    from_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    parsed_intent: Mapped[SmsIntent | None] = mapped_column(str_enum(SmsIntent, 20))
    resulting_ping_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pings.id"))
    raw_payload: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SmsOutboxEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sms_outbox"

    to_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose: Mapped[SmsOutboxPurpose] = mapped_column(str_enum(SmsOutboxPurpose, 32), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="infobip")
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[SmsOutboxStatus] = mapped_column(
        str_enum(SmsOutboxStatus, 20), nullable=False, default=SmsOutboxStatus.queued
    )
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1000))
    related_ping_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pings.id"))
    related_otp_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("otp_verifications.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
