import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import get_current_user
from app.models.user import User
from app.schemas.ping import PingOut
from app.schemas.user import UserMeOut, UserPublicOut, UserUpdateIn
from app.services import media_asset_service, ping_service
from app.services.visibility_service import can_view_location

router = APIRouter(prefix="/users", tags=["users"])


async def _build_user_me_out(db: AsyncSession, user: User) -> UserMeOut:
    asset = await media_asset_service.get_profile_photo_asset(db, user_id=user.id)
    return UserMeOut.model_validate(user).model_copy(
        update={"has_profile_photo": asset is not None}
    )


async def _build_user_public_out(db: AsyncSession, *, target: User, viewer_id: uuid.UUID) -> UserPublicOut:
    asset = await media_asset_service.get_profile_photo_asset(db, user_id=target.id)
    visible = await can_view_location(db, viewer_id=viewer_id, subject_id=target.id)
    out = UserPublicOut.model_validate(target)
    return out.model_copy(
        update={
            "has_profile_photo": asset is not None,
            "national_id_number": target.national_id_number if visible else None,
        }
    )


@router.get("/me", response_model=UserMeOut)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _build_user_me_out(db, user)


@router.patch("/me", response_model=UserMeOut)
async def update_me(
    body: UserUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return await _build_user_me_out(db, user)


@router.get("/me/pings", response_model=list[PingOut])
async def get_my_pings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pings = await ping_service.list_pings_for_subject(db, subject_user_id=user.id)
    return [await ping_service.serialize_ping(db, ping=p, viewer_id=user.id) for p in pings]


@router.put("/me/profile-photo", response_model=UserMeOut)
@limiter.limit("10/minute")
async def upload_profile_photo(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_bytes = await file.read()
    try:
        await media_asset_service.upload_profile_photo(
            db, user_id=user.id, raw_bytes=raw_bytes, content_type=file.content_type or ""
        )
    except media_asset_service.FileTooLarge:
        await db.rollback()
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo is too large")
    except media_asset_service.UnsupportedImageType:
        await db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File is not a supported image (JPEG/PNG/WEBP)")
    await db.commit()
    return await _build_user_me_out(db, user)


@router.delete("/me/profile-photo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_photo(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await media_asset_service.delete_profile_photo(db, user_id=user.id)
    await db.commit()


@router.get("/{user_id}/profile-photo")
async def get_profile_photo(
    user_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await media_asset_service.get_profile_photo_bytes_for_viewer(
        db, subject_user_id=user_id, viewer_id=user.id
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile photo, or you don't have access to it")
    photo_bytes, content_type = result
    return Response(content=photo_bytes, media_type=content_type)


@router.get("/{user_id}", response_model=UserPublicOut)
async def get_user(
    user_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return await _build_user_public_out(db, target=target, viewer_id=user.id)
