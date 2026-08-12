from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import require_responder
from app.models.user import User
from app.schemas.search import PersonSearchResultOut
from app.services import matching_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/people", response_model=list[PersonSearchResultOut])
@limiter.limit("20/minute")
async def search_people(
    request: Request,
    phone: str | None = None,
    name: str | None = None,
    _: User = Depends(require_responder),
    db: AsyncSession = Depends(get_db),
):
    # A direct PII lookup over a vulnerable population -- restricted to verified
    # responders/admins (require_responder) AND rate-limited, so neither a
    # compromised nor a legitimately-verified responder account can scrape the
    # full directory.
    results = await matching_service.search_people(db, phone=phone, name=name)
    return [PersonSearchResultOut(**r) for r in results]
