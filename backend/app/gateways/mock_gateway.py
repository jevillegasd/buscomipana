import logging
import uuid

from app.gateways.base import GatewaySendResult, NotificationGateway, render_otp_message

logger = logging.getLogger("gateways.mock")

# In-memory, process-local record of the last thing sent to each phone number.
# Backs the local-dev-only `_debug/last-otp` endpoint so a developer can read an
# OTP code without digging through logs. Never used outside ENV=local.
_last_sent_by_phone: dict[str, str] = {}


class MockGateway(NotificationGateway):
    async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult:
        body = render_otp_message(code)
        return await self.send_sms(to_phone_number, body, idempotency_key=f"otp:{to_phone_number}:{code}")

    async def send_sms(self, to_phone_number: str, body: str, *, idempotency_key: str) -> GatewaySendResult:
        _last_sent_by_phone[to_phone_number] = body
        logger.info("MOCK SMS to %s: %s", to_phone_number, body)
        return GatewaySendResult(
            provider="mock", provider_message_id=str(uuid.uuid4()), accepted=True
        )


def get_last_sent_message(phone_number: str) -> str | None:
    return _last_sent_by_phone.get(phone_number)
