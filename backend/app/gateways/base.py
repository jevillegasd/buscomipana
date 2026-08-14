from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import get_settings
from app.models.enums import Channel

__all__ = [
    "MAX_SMS_SEGMENT_CHARS",
    "Channel",
    "GatewaySendResult",
    "InboundChannelEvent",
    "NotificationGateway",
    "fit_single_sms",
    "render_otp_message",
    "to_gsm7",
]

# A single (non-concatenated) SMS segment under the GSM 03.38 default
# alphabet holds 160 characters; switch to UCS-2 (any non-GSM-7 character)
# and that drops to 70. Every outbound message in this app is composed
# through fit_single_sms so it always ships as one segment, one send.
MAX_SMS_SEGMENT_CHARS = 160

_GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ"
    ' !"#¤%&\'()*+,-./0123456789:;<=>?'
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_GSM7_CHARS = set(_GSM7_BASIC)

# Spanish acute-accented vowels (á í ó ú and uppercase) have no GSM-7
# representation at all -- not even in the extension table -- so they're
# transliterated rather than left in. Typographic quotes/dashes/ellipsis are
# the other characters people's phone keyboards commonly produce in free-text
# input that would otherwise silently force UCS-2 encoding.
_GSM7_TRANSLITERATIONS = {
    "á": "a", "Á": "A", "í": "i", "Í": "I", "ó": "o", "Ó": "O", "ú": "u", "Ú": "U",
    "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
}


def to_gsm7(text: str) -> str:
    """Best-effort transliteration into the GSM 03.38 default alphabet.
    Characters with no GSM-7 equivalent and no entry in
    _GSM7_TRANSLITERATIONS are dropped rather than passed through -- a single
    stray character (emoji, ⚠, etc.) would otherwise force the whole message
    into UCS-2 and cut the single-segment budget from 160 to 70 characters."""
    return "".join(
        ch if ch in _GSM7_CHARS else _GSM7_TRANSLITERATIONS.get(ch, "") for ch in text
    )


def fit_single_sms(text: str, max_len: int = MAX_SMS_SEGMENT_CHARS) -> str:
    """GSM-7-transliterates and hard-truncates so the result always fits a
    single SMS segment, never triggering a (costlier, less reliable)
    multi-part concatenated send."""
    return to_gsm7(text)[:max_len]


def render_otp_message(code: str) -> str:
    # Single source of truth for the OTP SMS body text -- used by every
    # gateway implementation and by auth_service (for the sms_outbox audit
    # record) so the brand name only ever needs to change in one place.
    # Spanish: this is user-facing copy sent to the end user's phone, same as
    # the frontend, not backend-internal text -- see docs/identity/es.md.
    return fit_single_sms(f"Tu código de {get_settings().app_name} es {code}")


@dataclass
class GatewaySendResult:
    provider: str
    provider_message_id: str
    accepted: bool
    error: str | None = None
    # Set only by gateways where the *provider* generates and owns the OTP
    # value (see NotificationGateway.verifies_otp_externally) -- an opaque
    # handle (e.g. Infobip's pinId) auth_service persists on the
    # OtpVerification row instead of a locally-hashed code, and passes back
    # to verify_otp_external to check what the user typed.
    external_reference: str | None = None


@dataclass
class InboundChannelEvent:
    """Normalized shape for any inbound channel event (SMS today, IVR/USSD later).

    channel_ingest_service.ingest() consumes this and funnels every channel into
    the same ping_service.create_ping() call the web REST endpoint uses.
    """

    channel: Channel
    from_phone_number: str
    provider_message_id: str
    raw_text: str | None = None
    dtmf_digits: str | None = None
    metadata: dict | None = None


class NotificationGateway(ABC):
    """Provider-agnostic interface for outbound OTP/SMS/voice delivery.

    Swappable per environment via SMS_GATEWAY (mock locally, infobip in
    staging/prod). Adding a new provider means implementing this interface,
    not touching any calling code.
    """

    # True for gateways whose send_otp routes through a provider-managed OTP
    # product (Infobip's 2FA API) instead of sending a code this app
    # generated itself. When True, auth_service skips generating/hashing its
    # own code for send_otp and, on verify, calls verify_otp_external instead
    # of comparing against OtpVerification.code_hash -- the provider is
    # authoritative for whether the code the user typed is correct.
    verifies_otp_externally: bool = False

    @abstractmethod
    async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult: ...

    @abstractmethod
    async def send_sms(self, to_phone_number: str, body: str, *, idempotency_key: str) -> GatewaySendResult: ...

    async def verify_otp_external(self, *, external_reference: str, code: str) -> bool:
        """Only implemented by gateways with verifies_otp_externally = True."""
        raise NotImplementedError(
            "verify_otp_external is only implemented by gateways with verifies_otp_externally = True"
        )

    async def place_ivr_call(self, to_phone_number: str, script_id: str) -> GatewaySendResult:
        raise NotImplementedError("IVR/voice calling is not implemented in the MVP; reserved for a later phase")
