import httpx
import pytest

from app.gateways.twilio_gateway import TwilioGateway


def _gateway(handler, **overrides) -> TwilioGateway:
    kwargs = {
        "account_sid": "AC123",
        "auth_token": "secret",
        "from_number": "+15005550006",
        "transport": httpx.MockTransport(handler),
    }
    kwargs.update(overrides)
    return TwilioGateway(**kwargs)


@pytest.mark.asyncio
async def test_send_sms_uses_from_number_when_no_messaging_service_configured():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/2010-04-01/Accounts/AC123/Messages.json"
        form = dict(httpx.QueryParams(request.content.decode()))
        assert form["To"] == "+573001234567"
        assert form["Body"] == "hola"
        assert form["From"] == "+15005550006"
        assert "MessagingServiceSid" not in form
        return httpx.Response(201, json={"sid": "SM123"})

    gateway = _gateway(handler)
    result = await gateway.send_sms("+573001234567", "hola", idempotency_key="k1")

    assert result.accepted is True
    assert result.provider == "twilio"
    assert result.provider_message_id == "SM123"


@pytest.mark.asyncio
async def test_send_sms_prefers_messaging_service_sid_over_from_number():
    def handler(request: httpx.Request) -> httpx.Response:
        form = dict(httpx.QueryParams(request.content.decode()))
        assert form["MessagingServiceSid"] == "MG999"
        assert "From" not in form
        return httpx.Response(201, json={"sid": "SM124"})

    gateway = _gateway(handler, messaging_service_sid="MG999")
    result = await gateway.send_sms("+573001234567", "hola", idempotency_key="k1")

    assert result.accepted is True
    assert result.provider_message_id == "SM124"


@pytest.mark.asyncio
async def test_send_sms_not_accepted_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 21211, "message": "Invalid 'To' Phone Number"})

    gateway = _gateway(handler)
    result = await gateway.send_sms("+573001234567", "hola", idempotency_key="k1")

    assert result.accepted is False
    assert result.error
    assert result.provider_message_id == ""


@pytest.mark.asyncio
async def test_send_otp_renders_code_into_message_and_sends_as_sms():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        form = dict(httpx.QueryParams(request.content.decode()))
        captured["body"] = form["Body"]
        return httpx.Response(201, json={"sid": "SM125"})

    gateway = _gateway(handler)
    result = await gateway.send_otp("+573001234567", "654321")

    assert result.accepted is True
    assert "654321" in captured["body"]
