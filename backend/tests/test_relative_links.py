import pytest

from tests.conftest import signup_and_login

PHONE_A = "+573009991001"
PHONE_UNCLAIMED = "+573009991002"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_relative_link_to_unregistered_number_is_created_unclaimed(client):
    a = await signup_and_login(client, PHONE_A)

    resp = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": PHONE_UNCLAIMED},
        headers=auth_headers(a),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["target_user_id"] is None
    assert body["target_phone_number"] == PHONE_UNCLAIMED
    assert body["status"] == "pending"

    # Shows up in the requester's own list even though nobody has claimed it.
    resp = await client.get("/api/v1/relative-links", headers=auth_headers(a))
    assert resp.status_code == 200, resp.text
    assert any(link["id"] == body["id"] for link in resp.json())


@pytest.mark.asyncio
async def test_unclaimed_relative_link_resolves_and_can_be_accepted_on_signup(client):
    a = await signup_and_login(client, PHONE_A)
    create = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": PHONE_UNCLAIMED},
        headers=auth_headers(a),
    )
    link_id = create.json()["id"]

    # The unclaimed number signs up -- the pending link should now be claimed
    # (target_user_id filled in) and visible/acceptable from their side.
    b = await signup_and_login(client, PHONE_UNCLAIMED)

    resp = await client.get("/api/v1/relative-links", headers=auth_headers(b))
    assert resp.status_code == 200, resp.text
    [link] = [link for link in resp.json() if link["id"] == link_id]
    assert link["target_user_id"] == b["user_id"]
    assert link["target_phone_number"] is None
    assert link["status"] == "pending"

    resp = await client.post(f"/api/v1/relative-links/{link_id}/accept", headers=auth_headers(b))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_duplicate_unclaimed_request_to_same_number_is_rejected(client):
    a = await signup_and_login(client, PHONE_A)
    resp = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": PHONE_UNCLAIMED},
        headers=auth_headers(a),
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": PHONE_UNCLAIMED},
        headers=auth_headers(a),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cannot_request_unclaimed_link_to_own_number(client):
    a = await signup_and_login(client, PHONE_A)
    resp = await client.post(
        "/api/v1/relative-links",
        json={"target_phone_number": PHONE_A},
        headers=auth_headers(a),
    )
    assert resp.status_code == 400
