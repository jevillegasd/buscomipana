import asyncio
import logging

import httpx

from app.core.config import get_settings
from app.gateways.base import GatewaySendResult, NotificationGateway

logger = logging.getLogger("gateways.infobip")

settings = get_settings()


class InfobipGateway(NotificationGateway):
    """Real Infobip adapter.

    Ping/pong status notifications go through the generic SMS "advanced
    text" endpoint (send_sms). OTP codes go through Infobip's dedicated 2FA
    product (/2fa/2/...) instead -- several Colombian carriers reject
    OTP-classified traffic sent over the generic /sms/2/... route with
    "Account not provisioned for the requested channel" (error 592,
    REJECTED_NETWORK), requiring it to originate from Infobip's dedicated
    2FA infrastructure instead. Under that product Infobip generates and
    owns the actual PIN value -- this app never sees it -- so
    verifies_otp_externally is True and verify_otp_external calls Infobip's
    own verify endpoint rather than comparing a locally hashed code.

    Endpoint paths/payload shapes below are per Infobip's documented 2FA v2
    API; reconfirm against the current Infobip API docs / account dashboard
    if sends or verifies start failing with an unexpected shape, since
    providers do revise these occasionally.
    """

    verifies_otp_externally = True

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        sender_id: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = (base_url or settings.infobip_base_url).rstrip("/")
        self.api_key = api_key or settings.infobip_api_key
        self.sender_id = sender_id or settings.infobip_sender_id
        # Injectable only for tests (httpx.MockTransport) -- None means httpx's
        # real network transport, unchanged in production.
        self._transport = transport
        self._application_id: str | None = settings.infobip_2fa_application_id or None
        self._message_id: str | None = settings.infobip_2fa_message_id or None
        self._provision_lock = asyncio.Lock()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=10.0, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"App {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _ensure_2fa_application(self, client: httpx.AsyncClient) -> tuple[str, str]:
        """Returns (applicationId, messageId), provisioning them via
        Infobip's API on first use if not configured. Cached on this gateway
        instance (a process-lifetime singleton -- see gateways/factory.py)
        so a lost race under concurrent first requests is the only way this
        provisions more than once per process; the lock closes even that
        window."""
        if self._application_id and self._message_id:
            return self._application_id, self._message_id

        async with self._provision_lock:
            if self._application_id and self._message_id:
                return self._application_id, self._message_id

            app_response = await client.post(
                f"{self.base_url}/2fa/2/applications",
                headers=self._headers(),
                json={
                    "name": f"{settings.app_name} OTP",
                    "enabled": True,
                    "configuration": {
                        "pinAttempts": settings.otp_max_attempts,
                        "allowMultiplePinVerifications": False,
                        "pinTimeToLive": f"{settings.otp_ttl_minutes}m",
                    },
                },
            )
            app_response.raise_for_status()
            application_id = app_response.json()["applicationId"]

            message_response = await client.post(
                f"{self.base_url}/2fa/2/applications/{application_id}/messages",
                headers=self._headers(),
                json={
                    "pinType": "NUMERIC",
                    "messageText": f"Tu codigo de {settings.app_name} es {{{{pin}}}}",
                    "pinLength": settings.otp_code_length,
                    "senderId": self.sender_id,
                },
            )
            message_response.raise_for_status()
            message_id = message_response.json()["messageId"]

            self._application_id = application_id
            self._message_id = message_id
            logger.warning(
                "Auto-provisioned Infobip 2FA application %s / message template %s -- "
                "set INFOBIP_2FA_APPLICATION_ID / INFOBIP_2FA_MESSAGE_ID to reuse these "
                "instead of provisioning a new pair on every process restart.",
                application_id,
                message_id,
            )
            return application_id, message_id

    async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult:
        """`code` is unused here -- Infobip's 2FA product generates and owns
        the actual PIN (see class docstring). It stays in the signature only
        to satisfy NotificationGateway's shared interface; auth_service
        checks verifies_otp_externally and skips generating/hashing a code
        of its own before calling this."""
        try:
            async with self._client() as client:
                application_id, message_id = await self._ensure_2fa_application(client)
                response = await client.post(
                    f"{self.base_url}/2fa/2/pin/{application_id}/{message_id}",
                    headers=self._headers(),
                    json={"to": to_phone_number.lstrip("+")},
                )
            response.raise_for_status()
            pin_id = response.json()["pinId"]
            return GatewaySendResult(
                provider="infobip", provider_message_id=pin_id, accepted=True, external_reference=pin_id
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Infobip 2FA send_otp failed for %s: %s", to_phone_number, exc)
            return GatewaySendResult(provider="infobip", provider_message_id="", accepted=False, error=str(exc))

    async def verify_otp_external(self, *, external_reference: str, code: str) -> bool:
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self.base_url}/2fa/2/pin/{external_reference}/verify",
                    headers=self._headers(),
                    json={"pin": code},
                )
            # A pinId that's expired, already verified, or unknown to Infobip
            # (e.g. the 10-minute TTL lapsed) 404s -- that's just "wrong
            # code" from this app's perspective, not an error to propagate.
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return bool(response.json().get("verified"))
        except httpx.HTTPError as exc:
            logger.error("Infobip 2FA verify_otp_external failed for pin %s: %s", external_reference, exc)
            return False

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
        try:
            async with self._client() as client:
                response = await client.post(
                    f"{self.base_url}/sms/2/text/advanced", json=payload, headers=self._headers()
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
