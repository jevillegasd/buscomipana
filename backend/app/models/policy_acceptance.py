import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class PolicyAcceptance(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One row per privacy-policy acceptance -- the digital marker of consent
    required for Colombian Habeas Data (Ley 1581 de 2012) compliance. Rows are
    append-only: a user re-accepting (e.g. after a policy_version bump) adds a
    new row rather than overwriting the old one, so the acceptance history for
    every version a user ever agreed to stays intact for audit purposes."""

    __tablename__ = "policy_acceptances"
    __table_args__ = (Index("ix_policy_acceptances_user", "user_id", "accepted_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    policy_country: Mapped[str] = mapped_column(String(2), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
