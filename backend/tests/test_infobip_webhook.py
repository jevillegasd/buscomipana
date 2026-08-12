import pytest

from app.core.config import get_settings
from tests.conftest import signup_and_login

PHONE = "+573007777777"


@pytest.mark.asyncio
async def test_inbound_sms_ping_sos_creates_ping_and_is_idempotent(client):
    user = await signup_and_login(client, PHONE)
    secret = get_settings().infobip_webhook_shared_secret

    payload = {
        "results": [
            {
                "messageId": "msg-001",
                "from": PHONE.lstrip("+"),
                "to": "573000000000",
                "text": "PING SOS",
            }
        ]
    }

    resp = await client.post(
        "/api/v1/webhooks/infobip/sms/inbound",
        json=payload,
        headers={"X-Webhook-Secret": secret},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["processed"] == 1

    resp = await client.get(
        "/api/v1/users/me/pings", headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert resp.status_code == 200
    pings = resp.json()
    # Signup itself seeds one initial "ok" self-ping (see
    # auth_service.verify_login_otp), so this SMS ping is the second, most
    # recent entry (feed is ordered newest first).
    assert len(pings) == 2
    assert pings[0]["status"] == "distress"
    assert pings[0]["channel"] == "sms"

    # Re-delivery of the same provider message id must not create a duplicate ping.
    resp = await client.post(
        "/api/v1/webhooks/infobip/sms/inbound",
        json=payload,
        headers={"X-Webhook-Secret": secret},
    )
    assert resp.status_code == 200

    resp = await client.get(
        "/api/v1/users/me/pings", headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_inbound_sms_wrong_secret_rejected(client):
    resp = await client.post(
        "/api/v1/webhooks/infobip/sms/inbound",
        json={"results": []},
        headers={"X-Webhook-Secret": "wrong"},
    )
    assert resp.status_code == 401
