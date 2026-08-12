import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import (
    RelationshipType,
    RelativeLinkStatus,
    ResponderCredentialStatus,
)
from app.models.mixins import UUIDPrimaryKeyMixin
from app.models.types import str_enum


class RelativeLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "relative_links"
    __table_args__ = (
        UniqueConstraint("requester_user_id", "target_user_id", name="uq_relative_link_pair"),
        CheckConstraint("requester_user_id <> target_user_id", name="ck_relative_link_no_self"),
    )

    requester_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    relationship_label: Mapped[RelationshipType | None] = mapped_column(str_enum(RelationshipType, 20))
    status: Mapped[RelativeLinkStatus] = mapped_column(
        str_enum(RelativeLinkStatus, 20),
        nullable=False,
        default=RelativeLinkStatus.pending,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResponderCredential(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "responder_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    organization_name: Mapped[str] = mapped_column(String(200), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ResponderCredentialStatus] = mapped_column(
        str_enum(ResponderCredentialStatus, 20),
        nullable=False,
        default=ResponderCredentialStatus.pending,
    )
    verified_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(1000))
