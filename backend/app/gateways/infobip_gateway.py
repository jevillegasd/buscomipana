import logging

import httpx

from app.core.config import get_settings
from app.gateways.base import GatewaySendResult, NotificationGateway, render_otp_message

logger = logging.getLogger("gateways.infobip")

settings = get_settings()


class InfobipGateway(NotificationGateway):
    """Real Infobip SMS (and, later, Voice/IVR) adapter.

    Uses Infobip's SMS "advanced text" endpoint for both OTP delivery and ping/pong
    notifications -- there is no behavioral difference between them at the transport
    layer, only in the message body and how the caller reacts to failure.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None, sender_id: str | None = None):
        self.base_url = (base_url or settings.infobip_base_url).rstrip("/")
        self.api_key = api_key or settings.infobip_api_key
        self.sender_id = sender_id or settings.infobip_sender_id

    async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult:
        body = render_otp_message(code)
        return await self.send_sms(to_phone_number, body, idempotency_key=f"otp:{to_phone_number}:{code}")

    async def send_sms(self, to_phone_number: str, body: str, *, idempotency_key: str) -> GatewaySendResult:
        payload = {
            "messages": [
                {
                    "from": self.sender_id,
                    "destinations": [{"to": to_phone_number.lstrip("+")}],
                    "text": body,
                }
            ]
        }
        headers = {
            "Authorization": f"App {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sms/2/text/advanced", json=payload, headers=headers
                )
            response.raise_for_status()
            data = response.json()
            message_id = data["messages"][0]["messageId"]
            return GatewaySendResult(provider="infobip", provider_message_id=message_id, accepted=True)
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.error("Infobip send_sms failed for %s: %s", to_phone_number, exc)
            return GatewaySendResult(
                provider="infobip", provider_message_id="", accepted=False, error=str(exc)
            )
