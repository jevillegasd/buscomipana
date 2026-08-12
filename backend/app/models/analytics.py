from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Channel, PingStatus
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.types import str_enum


class PingAnalyticsEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ping_analytics_events"
    __table_args__ = (
        Index("ix_ping_analytics_created", "ping_created_at"),
        Index("ix_ping_analytics_subject_hash", "subject_hash"),
    )

    # HMAC-SHA256(user_id, pepper) — irreversible without the out-of-DB pepper.
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # HMAC-SHA256(ping_id, pepper) — a collision-free join key so
    # record_pong_latency() can find the exact row to update. Doesn't weaken
    # anonymity: reversing it still requires the pepper, and anyone who already
    # has both the pepper and read access to `pings` could deanonymize via
    # subject_user_id directly anyway, so this reveals nothing extra.
    ping_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    pepper_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[PingStatus] = mapped_column(str_enum(PingStatus, 20), nullable=False)
    channel: Mapped[Channel] = mapped_column(str_enum(Channel, 20), nullable=False)
    is_proxy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    ping_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_pong_latency_seconds: Mapped[int | None] = mapped_column(Integer)
