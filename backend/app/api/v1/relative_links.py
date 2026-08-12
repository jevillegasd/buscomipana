import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import get_current_user
from app.models.enums import RelativeLinkStatus
from app.models.user import User
from app.schemas.relative_link import RelativeLinkOut, RelativeLinkRequestIn
from app.services import relative_link_service

router = APIRouter(prefix="/relative-links", tags=["relative-links"])


@router.post("", response_model=RelativeLinkOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_relative_link(
    request: Request,
    body: RelativeLinkRequestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        link = await relative_link_service.request_link(
            db, requester=user, target_phone_number=body.target_phone_number,
            relationship_label=body.relationship_label,
        )
    except relative_link_service.CannotLinkSelf:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot create a relative link to yourself")
    except relative_link_service.LinkAlreadyExists:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A relative link already exists between these accounts")
    await db.commit()
    return link


@router.get("", response_model=list[RelativeLinkOut])
async def list_relative_links(
    status_filter: RelativeLinkStatus | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await relative_link_service.list_links(db, user=user, status_filter=status_filter)


@router.post("/{link_id}/accept", response_model=RelativeLinkOut)
async def accept_relative_link(
    link_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        link = await relative_link_service.respond_to_link(db, user=user, link_id=link_id, accept=True)
    except relative_link_service.NotAuthorizedForLink:
        await db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relative link not found")
    await db.commit()
    return link


@router.post("/{link_id}/decline", response_model=RelativeLinkOut)
async def decline_relative_link(
    link_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        link = await relative_link_service.respond_to_link(db, user=user, link_id=link_id, accept=False)
    except relative_link_service.NotAuthorizedForLink:
        await db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relative link not found")
    await db.commit()
    return link


@router.delete("/{link_id}", response_model=RelativeLinkOut)
async def revoke_relative_link(
    link_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        link = await relative_link_service.revoke_link(db, user=user, link_id=link_id)
    except relative_link_service.NotAuthorizedForLink:
        await db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relative link not found")
    await db.commit()
    return link
