from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import get_current_user
from app.models.user import User
from app.schemas.responder import ResponderApplyIn, ResponderCredentialOut
from app.services import responder_service

router = APIRouter(prefix="/responders", tags=["responders"])


@router.post("/apply", response_model=ResponderCredentialOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def apply_as_responder(
    request: Request,
    body: ResponderApplyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        credential = await responder_service.apply(
            db,
            user=user,
            organization_name=body.organization_name,
            credential_type=body.credential_type,
            notes=body.notes,
        )
    except responder_service.AlreadyApplied:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A responder application already exists for this account")
    await db.commit()
    return credential
