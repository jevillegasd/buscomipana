import pytest

from tests.conftest import signup_and_login

PHONE_A = "+573001111111"
PHONE_B = "+573002222222"
PHONE_C = "+573003333333"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_ping_location_gated_by_handshake_and_proxy_labeling(client):
    a = await signup_and_login(client, PHONE_A)
    b = await signup_and_login(client, PHONE_B)
    c = await signup_and_login(client, PHONE_C)

    # B requests a relative link to A; A accepts.
    resp = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": PHONE_A, "relationship_label": "sibling"},
        headers=auth_headers(b),
    )
    assert resp.status_code == 201, resp.text
    link_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/relative-links/{link_id}/accept", headers=auth_headers(a))
    assert resp.status_code == 200, resp.text

    # A self-pings OK with a location.
    resp = await client.post(
        "/api/v1/pings",
        json={"status": "ok", "latitude": 4.7110, "longitude": -74.0721},
        headers=auth_headers(a),
    )
    assert resp.status_code == 201, resp.text
    ping = resp.json()
    assert ping["is_proxy"] is False
    assert ping["subject_user_id"] == a["user_id"]

    # B (accepted relative) can see the location.
    resp = await client.get(f"/api/v1/pings/{ping['id']}", headers=auth_headers(b))
    assert resp.status_code == 200
    assert resp.json()["latitude"] == pytest.approx(4.7110)

    # C (unrelated) sees the status but not the location.
    resp = await client.get(f"/api/v1/pings/{ping['id']}", headers=auth_headers(c))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["latitude"] is None
    assert body["longitude"] is None

    # B files a proxy ping on behalf of A (e.g. A called B to relay distress).
    resp = await client.post(
        "/api/v1/pings",
        json={"subject_user_id": a["user_id"], "status": "distress", "message": "found injured"},
        headers=auth_headers(b),
    )
    assert resp.status_code == 201, resp.text
    proxy_ping = resp.json()
    assert proxy_ping["is_proxy"] is True
    assert proxy_ping["reported_by_user_id"] == b["user_id"]
    assert proxy_ping["subject_user_id"] == a["user_id"]

    # A pongs back directly on the proxy-reported ping.
    resp = await client.post(
        f"/api/v1/pings/{proxy_ping['id']}/pongs",
        json={"message": "I'm safe now", "audience": "directed"},
        headers=auth_headers(a),
    )
    assert resp.status_code == 201, resp.text
    pong = resp.json()
    assert pong["responder_user_id"] == a["user_id"]

    # Listing pongs requires authentication like every other ping/pong read.
    # The shared client still carries A's session cookie from the pong POST
    # above (cookie auth persists across requests, same as a real browser),
    # so it has to be cleared to actually exercise the anonymous case.
    client.cookies.clear()
    resp = await client.get(f"/api/v1/pings/{proxy_ping['id']}/pongs")
    assert resp.status_code == 401

    resp = await client.get(f"/api/v1/pings/{proxy_ping['id']}/pongs", headers=auth_headers(c))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
