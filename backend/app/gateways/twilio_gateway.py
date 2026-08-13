import logging

import httpx

from app.core.config import get_settings
from app.gateways.base import GatewaySendResult, NotificationGateway, render_otp_message

logger = logging.getLogger("gateways.twilio")

settings = get_settings()


class TwilioGateway(NotificationGateway):
    """Twilio adapter -- plain SMS via Twilio's Messages API. Alternate
    SMS_GATEWAY option for when a carrier/country blocks traffic on the
    primary provider (see InfobipGateway's docstring for the Colombian
    carrier rejection this is a fallback for).

    Twilio generates no OTP of its own here -- verifies_otp_externally stays
    at NotificationGateway's default (False), so auth_service generates and
    hashes the code locally exactly as it does for MockGateway/Infobip's
    generic send_sms path, and send_otp just renders that code into a normal
    SMS body.
    """

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
        messaging_service_sid: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.account_sid = account_sid or settings.twilio_account_sid
        self.auth_token = auth_token or settings.twilio_auth_token
        self.from_number = from_number or settings.twilio_from_number
        self.messaging_service_sid = messaging_service_sid or settings.twilio_messaging_service_sid
        # Injectable only for tests (httpx.MockTransport) -- None means httpx's
        # real network transport, unchanged in production.
        self._transport = transport

    def _base_url(self) -> str:
        return f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=10.0, transport=self._transport, auth=(self.account_sid, self.auth_token)
        )

    async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult:
        body = render_otp_message(code)
        return await self.send_sms(to_phone_number, body, idempotency_key=f"otp:{to_phone_number}:{code}")

    async def send_sms(self, to_phone_number: str, body: str, *, idempotency_key: str) -> GatewaySendResult:
        # Twilio wants a Messaging Service SID (lets Twilio pick/rotate senders
        # -- the recommended setup for A2P traffic) if one's configured;
        # otherwise fall back to a single fixed From number.
        payload = {"To": to_phone_number, "Body": body}
        if self.messaging_service_sid:
            payload["MessagingServiceSid"] = self.messaging_service_sid
        else:
            payload["From"] = self.from_number
        try:
            async with self._client() as client:
                response = await client.post(self._base_url(), data=payload)
            response.raise_for_status()
            data = response.json()
            return GatewaySendResult(provider="twilio", provider_message_id=data["sid"], accepted=True)
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Twilio send_sms failed for %s: %s", to_phone_number, exc)
            return GatewaySendResult(provider="twilio", provider_message_id="", accepted=False, error=str(exc))
