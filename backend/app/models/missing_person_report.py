import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import MissingPersonReportStatus, RelationshipType
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.types import str_enum


class MissingPersonReport(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "missing_person_reports"
    __table_args__ = (Index("ix_missing_person_reports_reporter", "reporter_user_id"),)

    reporter_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    subject_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    relationship: Mapped[RelationshipType | None] = mapped_column(str_enum(RelationshipType, 20))
    last_known_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    last_known_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    missing_since: Mapped[date | None] = mapped_column(Date)
    missing_location_description: Mapped[str | None] = mapped_column(String(300))
    last_known_clothing: Mapped[str | None] = mapped_column(String(500))
    body_marks: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[MissingPersonReportStatus] = mapped_column(
        str_enum(MissingPersonReportStatus, 20),
        nullable=False,
        default=MissingPersonReportStatus.open,
    )
    matched_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MissingPersonMatchCandidate(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "missing_person_match_candidates"
    __table_args__ = (
        UniqueConstraint("report_id", "candidate_user_id", name="uq_report_candidate"),
        Index("ix_candidates_report_score", "report_id", "combined_score"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missing_person_reports.id"), nullable=False
    )
    candidate_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    phone_similarity_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    name_similarity_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    location_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    combined_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    confirmed: Mapped[bool | None] = mapped_column(Boolean)
