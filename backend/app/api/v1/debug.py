from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.gateways.mock_gateway import get_last_sent_message

router = APIRouter(prefix="/_debug", tags=["debug"])

settings = get_settings()


@router.get("/last-otp")
async def last_otp(phone: str):
    if not settings.is_local:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    message = get_last_sent_message(phone)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No message sent to this number yet")
    return {"phone_number": phone, "message": message}
