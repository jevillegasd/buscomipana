import uuid

from sqlalchemy import (
    Boolean,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Channel, PingStatus, PongAudience
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.types import PortableJSON, str_enum


class Ping(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "pings"
    __table_args__ = (
        Index("ix_pings_subject_created", "subject_user_id", "created_at"),
        Index("ix_pings_reported_by_created", "reported_by_user_id", "created_at"),
    )

    subject_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Generated column: TRUE whenever the reporter is not the subject (proxy/third-party ping).
    # Computed at the DB layer so the flag can never be forgotten or spoofed by application code.
    is_proxy: Mapped[bool] = mapped_column(
        Boolean, Computed("reported_by_user_id IS DISTINCT FROM subject_user_id", persisted=True)
    )
    status: Mapped[PingStatus] = mapped_column(str_enum(PingStatus, 20), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    location_accuracy_m: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[Channel] = mapped_column(str_enum(Channel, 20), nullable=False)
    channel_metadata: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)


class Pong(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "pongs"
    __table_args__ = (Index("ix_pongs_ping_id", "ping_id"),)

    ping_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pings.id"), nullable=False)
    responder_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    audience: Mapped[PongAudience] = mapped_column(str_enum(PongAudience, 20), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    channel: Mapped[Channel] = mapped_column(str_enum(Channel, 20), nullable=False)
