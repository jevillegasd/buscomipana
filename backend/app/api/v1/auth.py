from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    OtpRequestIn,
    OtpVerifyIn,
    PhoneNumberChangeConfirmIn,
    PhoneNumberChangeRequestIn,
    RefreshIn,
    TokenPairOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()


def _set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    # HttpOnly so browser-side JS can never read these -- the frontend relies on
    # the browser sending them automatically (fetch credentials: "include")
    # rather than managing tokens itself. Non-browser clients keep using the
    # Bearer token from the JSON body instead; both are accepted by
    # deps.get_current_user / auth_service.rotate_session.
    response.set_cookie(
        settings.access_token_cookie_name,
        access_token,
        max_age=int(timedelta(minutes=settings.jwt_access_token_ttl_minutes).total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.refresh_token_cookie_name,
        refresh_token,
        max_age=int(timedelta(days=settings.jwt_refresh_token_ttl_days).total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.access_token_cookie_name, path="/")
    response.delete_cookie(settings.refresh_token_cookie_name, path="/api/v1/auth")


def _set_remember_device_cookie(response: Response, device_token: str) -> None:
    response.set_cookie(
        settings.remember_device_cookie_name,
        device_token,
        max_age=int(timedelta(days=settings.remember_device_ttl_days).total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def request_otp(request: Request, body: OtpRequestIn, response: Response, db: AsyncSession = Depends(get_db)):
    device_token = request.cookies.get(settings.remember_device_cookie_name)
    trusted_user = await auth_service.try_device_login(db, phone_number=body.phone_number, device_token=device_token)
    if trusted_user is not None:
        access_token, refresh_token = await auth_service.create_session(db, user=trusted_user)
        await db.commit()
        _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
        return {"detail": "Dispositivo de confianza, código omitido", "skipped_otp": True}

    try:
        await auth_service.request_login_otp(db, phone_number=body.phone_number, email=body.email)
    except auth_service.UnsupportedCountry:
        await db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Por ahora BuscoMiPana solo está disponible en Colombia y Emiratos Árabes Unidos.",
        )
    except auth_service.OtpCooldownActive as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Espera antes de solicitar otro código.",
                "retry_after_seconds": exc.retry_after_seconds,
            },
        )
    await db.commit()
    return {
        "detail": "OTP sent",
        "skipped_otp": False,
        "resend_cooldown_seconds": settings.otp_resend_cooldown_seconds,
    }


@router.post("/otp/verify", response_model=TokenPairOut)
@limiter.limit("10/minute")
async def verify_otp(
    request: Request, body: OtpVerifyIn, response: Response, db: AsyncSession = Depends(get_db)
):
    try:
        user, is_new_account = await auth_service.verify_login_otp(
            db, phone_number=body.phone_number, code=body.code
        )
    except auth_service.OtpError:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")

    access_token, refresh_token = await auth_service.create_session(db, user=user)
    await db.commit()
    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return TokenPairOut(
        access_token=access_token, refresh_token=refresh_token, is_new_account=is_new_account
    )


@router.post("/refresh", response_model=TokenPairOut)
async def refresh(request: Request, body: RefreshIn, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_token = body.refresh_token or request.cookies.get(settings.refresh_token_cookie_name)
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token provided")

    rotated = await auth_service.rotate_session(db, refresh_token=refresh_token)
    if rotated is None:
        await db.rollback()
        _clear_auth_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    access_token, new_refresh_token = rotated
    await db.commit()
    _set_auth_cookies(response, access_token=access_token, refresh_token=new_refresh_token)
    return TokenPairOut(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, body: RefreshIn, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_token = body.refresh_token or request.cookies.get(settings.refresh_token_cookie_name)
    if refresh_token is not None:
        device_token = await auth_service.logout_and_remember_device(db, refresh_token=refresh_token)
        await db.commit()
        if device_token is not None:
            _set_remember_device_cookie(response, device_token)
    _clear_auth_cookies(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await auth_service.revoke_all_sessions(db, user_id=user.id)
    await db.commit()
    _clear_auth_cookies(response)


@router.post("/phone-number/change/request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def request_phone_change(
    request: Request,
    body: PhoneNumberChangeRequestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.request_phone_change_otp(db, user=user, new_phone_number=body.new_phone_number)
    except auth_service.PhoneNumberTaken:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone number already in use")
    except auth_service.OtpCooldownActive as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Espera antes de solicitar otro código.",
                "retry_after_seconds": exc.retry_after_seconds,
            },
        )
    await db.commit()
    return {"detail": "OTP sent to new number", "resend_cooldown_seconds": settings.otp_resend_cooldown_seconds}


@router.post("/phone-number/change/confirm", response_model=TokenPairOut)
async def confirm_phone_change(
    body: PhoneNumberChangeConfirmIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.confirm_phone_change(
            db, user=user, new_phone_number=body.new_phone_number, code=body.code
        )
    except auth_service.OtpError:
        await db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")

    access_token, refresh_token = await auth_service.create_session(db, user=user)
    await db.commit()
    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return TokenPairOut(access_token=access_token, refresh_token=refresh_token)
