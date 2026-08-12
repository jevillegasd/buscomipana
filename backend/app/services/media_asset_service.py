import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import MediaAssetPurpose, MediaStorageBackend
from app.models.media import MediaAsset
from app.services.visibility_service import can_view_location
from app.storage.factory import get_storage
from app.storage.image_processing import (
    ALLOWED_INPUT_CONTENT_TYPES,
    InvalidImageError,
    process_image,
)

settings = get_settings()


class MediaAssetError(Exception):
    pass


class FileTooLarge(MediaAssetError):
    pass


class UnsupportedImageType(MediaAssetError):
    pass


class ConsentRequired(MediaAssetError):
    pass


def _new_storage_key(purpose: MediaAssetPurpose) -> str:
    return f"{purpose.value}/{uuid.uuid4()}.jpg"


async def _store_processed_image(
    db: AsyncSession,
    *,
    owner_user_id: uuid.UUID,
    purpose: MediaAssetPurpose,
    raw_bytes: bytes,
    content_type: str,
    missing_person_report_id: uuid.UUID | None = None,
    consent_public_use: bool = False,
    consent_ai_processing: bool = False,
) -> MediaAsset:
    if len(raw_bytes) > settings.media_max_upload_bytes:
        raise FileTooLarge()
    if content_type not in ALLOWED_INPUT_CONTENT_TYPES:
        raise UnsupportedImageType()
    try:
        clean_bytes, output_content_type = process_image(raw_bytes)
    except InvalidImageError as exc:
        raise UnsupportedImageType() from exc

    storage = get_storage()
    key = _new_storage_key(purpose)
    await storage.save(key=key, content=clean_bytes, content_type=output_content_type)

    asset = MediaAsset(
        owner_user_id=owner_user_id,
        missing_person_report_id=missing_person_report_id,
        purpose=purpose,
        storage_backend=MediaStorageBackend(settings.media_storage_backend),
        storage_key=key,
        content_type=output_content_type,
        file_size_bytes=len(clean_bytes),
        consent_public_use=consent_public_use,
        consent_ai_processing=consent_ai_processing,
        consent_recorded_at=datetime.now(UTC) if (consent_public_use or consent_ai_processing) else None,
    )
    db.add(asset)
    await db.flush()
    return asset


async def _delete_asset(db: AsyncSession, *, asset: MediaAsset) -> None:
    storage = get_storage()
    await storage.delete(key=asset.storage_key)
    await db.delete(asset)
    await db.flush()


async def get_profile_photo_asset(db: AsyncSession, *, user_id: uuid.UUID) -> MediaAsset | None:
    result = await db.execute(
        select(MediaAsset)
        .where(MediaAsset.owner_user_id == user_id, MediaAsset.purpose == MediaAssetPurpose.profile_photo)
        .order_by(MediaAsset.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_missing_person_photo_asset(db: AsyncSession, *, report_id: uuid.UUID) -> MediaAsset | None:
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.missing_person_report_id == report_id,
            MediaAsset.purpose == MediaAssetPurpose.missing_person_photo,
        )
    )
    return result.scalar_one_or_none()


async def upload_profile_photo(
    db: AsyncSession, *, user_id: uuid.UUID, raw_bytes: bytes, content_type: str
) -> MediaAsset:
    """Replaces any existing profile photo (deletes the old storage object +
    row) rather than keeping a history -- "one active profile photo" is the
    only semantic the rest of the app needs."""
    existing = await get_profile_photo_asset(db, user_id=user_id)
    asset = await _store_processed_image(
        db,
        owner_user_id=user_id,
        purpose=MediaAssetPurpose.profile_photo,
        raw_bytes=raw_bytes,
        content_type=content_type,
    )
    if existing is not None:
        await _delete_asset(db, asset=existing)
    return asset


async def delete_profile_photo(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    existing = await get_profile_photo_asset(db, user_id=user_id)
    if existing is not None:
        await _delete_asset(db, asset=existing)


async def get_profile_photo_bytes_for_viewer(
    db: AsyncSession, *, subject_user_id: uuid.UUID, viewer_id: uuid.UUID
) -> tuple[bytes, str] | None:
    """Same trust boundary as location (visibility_service.can_view_location):
    self, an accepted relative link, or a verified responder. A profile photo
    is at least as identifying as a lat/lng pair."""
    if not await can_view_location(db, viewer_id=viewer_id, subject_id=subject_user_id):
        return None
    asset = await get_profile_photo_asset(db, user_id=subject_user_id)
    if asset is None:
        return None
    storage = get_storage()
    return await storage.read(key=asset.storage_key), asset.content_type


async def upload_missing_person_photo(
    db: AsyncSession,
    *,
    reporter_id: uuid.UUID,
    report_id: uuid.UUID,
    raw_bytes: bytes,
    content_type: str,
    consent_public_use: bool,
    consent_ai_processing: bool,
) -> MediaAsset:
    """Consent is mandatory here, unlike the profile photo -- this image is
    shown to any authenticated user searching for the subject (matching
    missing_person_reports' existing open-to-any-authenticated-user
    visibility) and is the intended input for the future AI face-matching
    feature, so both uses must be explicitly agreed to before we accept the
    upload at all."""
    if not (consent_public_use and consent_ai_processing):
        raise ConsentRequired()

    existing = await get_missing_person_photo_asset(db, report_id=report_id)
    asset = await _store_processed_image(
        db,
        owner_user_id=reporter_id,
        purpose=MediaAssetPurpose.missing_person_photo,
        raw_bytes=raw_bytes,
        content_type=content_type,
        missing_person_report_id=report_id,
        consent_public_use=True,
        consent_ai_processing=True,
    )
    if existing is not None:
        await _delete_asset(db, asset=existing)
    return asset


async def get_missing_person_photo_bytes(db: AsyncSession, *, report_id: uuid.UUID) -> tuple[bytes, str] | None:
    asset = await get_missing_person_photo_asset(db, report_id=report_id)
    if asset is None:
        return None
    storage = get_storage()
    return await storage.read(key=asset.storage_key), asset.content_type
