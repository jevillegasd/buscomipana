from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import CALLING_CODE_TO_COUNTRY, resolve_country
from app.core.database import get_db
from app.core.limiter import get_client_ip
from app.deps import get_current_user
from app.models.user import User
from app.schemas.policy import PolicyAcceptanceOut, PolicyOut, TermsOut
from app.services import policy_service

router = APIRouter(prefix="/policy", tags=["policy"])

_SUPPORTED_COUNTRIES = set(CALLING_CODE_TO_COUNTRY.values())


@router.get("/privacy", response_model=PolicyOut)
async def get_privacy_policy(country: str = Query("CO")):
    """Public and unauthenticated -- this is what the login screen's footer
    link opens before anyone has signed in, so it must not require a
    session. Defaults to Colombia, the current flagship market, when no
    country is specified."""
    country = country.upper()
    if country not in _SUPPORTED_COUNTRIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported country code")
    document = policy_service.get_policy_for_country(country)
    return PolicyOut(
        country=country,
        version=document.version,
        title=document.title,
        content=policy_service.get_policy_content(document),
    )


@router.get("/privacy/me", response_model=PolicyOut)
async def get_my_privacy_policy(user: User = Depends(get_current_user)):
    country = resolve_country(user.phone_number)
    if country is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported country for this account")
    document = policy_service.get_policy_for_country(country)
    return PolicyOut(
        country=country,
        version=document.version,
        title=document.title,
        content=policy_service.get_policy_content(document),
    )


@router.get("/terms", response_model=TermsOut)
async def get_terms_of_service():
    """Public and unauthenticated, same as /privacy -- linked next to the
    privacy policy on the login screen. One document, no per-country variant
    and no acceptance gate (unlike the privacy policy's Habeas Data consent
    requirement)."""
    document = policy_service.TERMS_OF_SERVICE
    return TermsOut(
        version=document.version,
        title=document.title,
        content=policy_service.get_policy_content(document),
    )


@router.post("/privacy/accept", response_model=PolicyAcceptanceOut)
async def accept_privacy_policy(
    request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        acceptance = await policy_service.record_acceptance(
            db,
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError:
        await db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported country for this account")
    await db.commit()
    return PolicyAcceptanceOut(
        country=acceptance.policy_country, version=acceptance.policy_version, accepted_at=acceptance.accepted_at
    )
