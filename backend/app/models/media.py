import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import MediaAssetPurpose, MediaStorageBackend
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.types import str_enum


class MediaAsset(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Single table backing both profile photos and missing-person-report
    photos, so storage/consent/visibility logic lives in one place
    (media_asset_service.py) instead of being duplicated per feature.

    No FK from users/missing_person_reports pointing *in* here -- the "current
    photo" is found by querying the most recent row for
    (owner_user_id, purpose), same pattern as matching_service._latest_ping_location.
    That sidesteps a circular FK (this table already points at both) and makes
    "replace my photo" a plain insert instead of an update-then-cleanup.

    Never served directly from storage: always through an app endpoint that
    re-checks visibility (see visibility_service.can_view_location for
    profile photos; missing-person photos are intentionally open to any
    authenticated user, matching report visibility -- that's the point of the
    public/AI-processing consent captured below)."""

    __tablename__ = "media_assets"
    __table_args__ = (Index("ix_media_assets_owner_purpose", "owner_user_id", "purpose", "created_at"),)

    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Set only when purpose == missing_person_photo; identifies which report
    # this photo belongs to (a reporter can have many reports, each with its
    # own subject photo, so owner_user_id alone isn't enough to disambiguate).
    missing_person_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missing_person_reports.id"), unique=True
    )
    purpose: Mapped[MediaAssetPurpose] = mapped_column(str_enum(MediaAssetPurpose, 30), nullable=False)
    storage_backend: Mapped[MediaStorageBackend] = mapped_column(str_enum(MediaStorageBackend, 10), nullable=False)
    # Opaque, unguessable path/key within the storage backend -- never a
    # publicly-resolvable URL by itself.
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Only meaningful (and only ever set true) for missing_person_photo --
    # required before that upload is accepted at all. Profile photos leave
    # these false; they're never publicly broadcast the way a missing-person
    # flyer is.
    consent_public_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_ai_processing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
