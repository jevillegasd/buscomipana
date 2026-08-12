import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import get_current_user
from app.models.enums import Channel
from app.models.user import User
from app.schemas.ping import PingCreateIn, PingOut, PongCreateIn, PongOut
from app.services import ping_service, pong_service

router = APIRouter(prefix="/pings", tags=["pings"])


@router.post("", response_model=PingOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_ping(
    request: Request, body: PingCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        ping = await ping_service.create_ping(
            db,
            reported_by_user_id=user.id,
            subject_user_id=body.subject_user_id,
            status=body.status,
            message=body.message,
            latitude=body.latitude,
            longitude=body.longitude,
            location_accuracy_m=body.location_accuracy_m,
            channel=Channel.web,
        )
    except ping_service.SubjectNotFound:
        await db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject user not found")
    await db.commit()
    return await ping_service.serialize_ping(db, ping=ping, viewer_id=user.id)


@router.get("/{ping_id}", response_model=PingOut)
async def get_ping(
    ping_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        ping = await ping_service.get_ping(db, ping_id=ping_id)
    except ping_service.PingNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ping not found")
    return await ping_service.serialize_ping(db, ping=ping, viewer_id=user.id)


@router.get("", response_model=list[PingOut])
async def list_pings(
    subject_user_id: uuid.UUID,
    since: datetime | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pings = await ping_service.list_pings_for_subject(db, subject_user_id=subject_user_id, since=since)
    return [await ping_service.serialize_ping(db, ping=p, viewer_id=user.id) for p in pings]


@router.post("/{ping_id}/pongs", response_model=PongOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_pong(
    request: Request,
    ping_id: uuid.UUID,
    body: PongCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        pong = await pong_service.create_pong(
            db,
            ping_id=ping_id,
            responder_user_id=user.id,
            message=body.message,
            audience=body.audience,
            channel=Channel.web,
        )
    except pong_service.PingNotFoundForPong:
        await db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ping not found")
    await db.commit()
    return pong


@router.get("/{ping_id}/pongs", response_model=list[PongOut])
async def list_pongs(
    ping_id: uuid.UUID, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await pong_service.list_pongs_for_ping(db, ping_id=ping_id)
