import pytest

from app.services import auth_service
from tests.conftest import signup_and_login

PHONE_ADMIN = "+573001234000"
PHONE_SUBJECT = "+573001234001"
PHONE_RESPONDER = "+573001234002"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_verified_responder_can_view_location_without_a_relative_link(client, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "admin_phone_numbers", PHONE_ADMIN)

    admin = await signup_and_login(client, PHONE_ADMIN)
    subject = await signup_and_login(client, PHONE_SUBJECT)
    responder = await signup_and_login(client, PHONE_RESPONDER)

    resp = await client.post(
        "/api/v1/pings",
        json={"status": "distress", "latitude": 6.2442, "longitude": -75.5812},
        headers=auth_headers(subject),
    )
    assert resp.status_code == 201, resp.text
    ping_id = resp.json()["id"]

    # Before applying/verification: no relation, so location is hidden.
    resp = await client.get(f"/api/v1/pings/{ping_id}", headers=auth_headers(responder))
    assert resp.status_code == 200
    assert resp.json()["latitude"] is None

    # Non-admin cannot list pending responder applications.
    resp = await client.get("/api/v1/admin/responders/pending", headers=auth_headers(subject))
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/responders/apply",
        json={"organization_name": "Cruz Roja", "credential_type": "red_cross"},
        headers=auth_headers(responder),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending"

    # Still pending -> still no location access.
    resp = await client.get(f"/api/v1/pings/{ping_id}", headers=auth_headers(responder))
    assert resp.json()["latitude"] is None

    resp = await client.get("/api/v1/admin/responders/pending", headers=auth_headers(admin))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1

    resp = await client.post(
        f"/api/v1/admin/responders/{responder['user_id']}/verify", headers=auth_headers(admin)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "verified"

    # Now verified -> location becomes visible.
    resp = await client.get(f"/api/v1/pings/{ping_id}", headers=auth_headers(responder))
    assert resp.status_code == 200
    assert resp.json()["latitude"] == pytest.approx(6.2442)

    # Revoke and confirm access is pulled immediately.
    resp = await client.post(
        f"/api/v1/admin/responders/{responder['user_id']}/revoke", headers=auth_headers(admin)
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/pings/{ping_id}", headers=auth_headers(responder))
    assert resp.json()["latitude"] is None
