from functools import lru_cache

from app.core.config import get_settings
from app.gateways.base import NotificationGateway
from app.gateways.infobip_gateway import InfobipGateway
from app.gateways.mock_gateway import MockGateway
from app.gateways.twilio_gateway import TwilioGateway


@lru_cache
def get_gateway() -> NotificationGateway:
    settings = get_settings()
    if settings.sms_gateway == "infobip":
        return InfobipGateway()
    if settings.sms_gateway == "twilio":
        return TwilioGateway()
    return MockGateway()
