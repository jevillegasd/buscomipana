import httpx
import pytest

from app.gateways.infobip_gateway import InfobipGateway


def _gateway(handler) -> InfobipGateway:
    return InfobipGateway(
        base_url="https://api.infobip.com",
        api_key="secret",
        sender_id="Busco",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_send_otp_auto_provisions_application_and_sends_pin():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/2fa/2/applications":
            return httpx.Response(200, json={"applicationId": "app-1"})
        if request.url.path == "/2fa/2/applications/app-1/messages":
            return httpx.Response(200, json={"messageId": "msg-1"})
        if request.url.path == "/2fa/2/pin":
            import json as _json

            body = _json.loads(request.content)
            assert body["applicationId"] == "app-1"
            assert body["messageId"] == "msg-1"
            assert body["to"] in ("573001234567", "573001234568")
            return httpx.Response(200, json={"pinId": "pin-1"})
        raise AssertionError(f"unexpected request to {request.url.path}")

    gateway = _gateway(handler)

    result = await gateway.send_otp("+573001234567", "unused")

    assert result.accepted is True
    assert result.external_reference == "pin-1"
    assert calls == [
        "/2fa/2/applications",
        "/2fa/2/applications/app-1/messages",
        "/2fa/2/pin",
    ]

    # A second send reuses the now-cached application/message ids instead of
    # provisioning a new pair every time.
    calls.clear()
    result_2 = await gateway.send_otp("+573001234568", "unused")
    assert result_2.external_reference == "pin-1"
    assert calls == ["/2fa/2/pin"]


@pytest.mark.asyncio
async def test_send_otp_skips_provisioning_when_ids_preconfigured():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/2fa/2/pin"
        return httpx.Response(200, json={"pinId": "pin-9"})

    gateway = _gateway(handler)
    gateway._application_id = "preset-app"
    gateway._message_id = "preset-msg"

    result = await gateway.send_otp("+573001234567", "unused")
    assert result.external_reference == "pin-9"


@pytest.mark.asyncio
async def test_send_otp_not_accepted_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    gateway = _gateway(handler)

    result = await gateway.send_otp("+573001234567", "unused")
    assert result.accepted is False
    assert result.error
    assert result.external_reference is None


@pytest.mark.asyncio
async def test_verify_otp_external_true_and_false():
    verified_value = {"verified": True}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/2fa/2/pin/pin-1/verify"
        return httpx.Response(200, json=verified_value)

    gateway = _gateway(handler)

    assert await gateway.verify_otp_external(external_reference="pin-1", code="123456") is True

    verified_value["verified"] = False
    assert await gateway.verify_otp_external(external_reference="pin-1", code="000000") is False


@pytest.mark.asyncio
async def test_verify_otp_external_404_is_not_verified():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"requestError": {}})

    gateway = _gateway(handler)

    assert await gateway.verify_otp_external(external_reference="missing-pin", code="123456") is False
