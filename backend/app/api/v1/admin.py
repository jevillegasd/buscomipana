import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import require_admin
from app.models.user import User
from app.schemas.responder import ResponderCredentialOut
from app.services import responder_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/responders/pending", response_model=list[ResponderCredentialOut])
async def list_pending_responders(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await responder_service.list_pending(db)


@router.post("/responders/{user_id}/verify", response_model=ResponderCredentialOut)
async def verify_responder(
    user_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    try:
        credential = await responder_service.verify(db, user_id=user_id, admin=admin)
    except responder_service.CredentialNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No responder application for that user")
    await db.commit()
    return credential


@router.post("/responders/{user_id}/revoke", response_model=ResponderCredentialOut)
async def revoke_responder(
    user_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    try:
        credential = await responder_service.revoke(db, user_id=user_id, admin=admin)
    except responder_service.CredentialNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No responder application for that user")
    await db.commit()
    return credential
