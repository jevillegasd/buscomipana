import pytest

from app.gateways.base import GatewaySendResult, NotificationGateway
from app.services import auth_service


class FakeExternalGateway(NotificationGateway):
    """Stands in for InfobipGateway's 2FA mode -- the provider (not this
    app) generates and owns the OTP value, so verification has to go through
    verify_otp_external rather than a locally hashed code."""

    verifies_otp_externally = True

    def __init__(self, correct_code: str):
        self.correct_code = correct_code
        self.sent: list[tuple[str, str]] = []
        self.verify_calls: list[tuple[str, str]] = []

    async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult:
        pin_id = f"pin-for-{to_phone_number}"
        self.sent.append((to_phone_number, pin_id))
        return GatewaySendResult(
            provider="fake", provider_message_id=pin_id, accepted=True, external_reference=pin_id
        )

    async def send_sms(self, to_phone_number: str, body: str, *, idempotency_key: str) -> GatewaySendResult:
        raise NotImplementedError("not used by this test")

    async def verify_otp_external(self, *, external_reference: str, code: str) -> bool:
        self.verify_calls.append((external_reference, code))
        return code == self.correct_code


@pytest.mark.asyncio
async def test_login_via_externally_verified_gateway_rejects_wrong_code_then_accepts_right_one(
    client, monkeypatch
):
    fake_gateway = FakeExternalGateway(correct_code="654321")
    monkeypatch.setattr(auth_service, "get_gateway", lambda: fake_gateway)

    phone = "+573001239999"
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202, resp.text
    assert fake_gateway.sent == [(phone, f"pin-for-{phone}")]

    resp = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "code": "000000"})
    assert resp.status_code == 400
    assert fake_gateway.verify_calls == [(f"pin-for-{phone}", "000000")]

    resp = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "code": "654321"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_new_account"] is True


@pytest.mark.asyncio
async def test_verify_fails_cleanly_when_the_original_send_itself_failed(client, monkeypatch):
    class FailingGateway(FakeExternalGateway):
        async def send_otp(self, to_phone_number: str, code: str) -> GatewaySendResult:
            return GatewaySendResult(provider="fake", provider_message_id="", accepted=False, error="boom")

    failing_gateway = FailingGateway(correct_code="000000")
    monkeypatch.setattr(auth_service, "get_gateway", lambda: failing_gateway)

    phone = "+573001238888"
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert resp.status_code == 202, resp.text

    # No external_reference and no code_hash were ever recorded -- there's
    # nothing to check the submitted code against, so it must fail cleanly
    # (400) rather than raising an unhandled error.
    resp = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "code": "000000"})
    assert resp.status_code == 400
    assert failing_gateway.verify_calls == []
