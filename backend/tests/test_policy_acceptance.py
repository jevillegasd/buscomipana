import pytest

from tests.conftest import signup_and_login

PHONE = "+573001234580"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_privacy_policy_is_public_and_defaults_to_colombia(client):
    resp = await client.get("/api/v1/policy/privacy")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["country"] == "CO"
    assert "Hábeas Data" in body["content"] or "Habeas Data" in body["content"]


@pytest.mark.asyncio
async def test_privacy_policy_rejects_unsupported_country(client):
    resp = await client.get("/api/v1/policy/privacy", params={"country": "US"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_new_user_needs_policy_acceptance_until_they_accept(client):
    a = await signup_and_login(client, PHONE)

    resp = await client.get("/api/v1/users/me", headers=auth_headers(a))
    assert resp.status_code == 200, resp.text
    assert resp.json()["needs_privacy_policy_acceptance"] is True

    resp = await client.get("/api/v1/policy/privacy/me", headers=auth_headers(a))
    assert resp.status_code == 200, resp.text
    assert resp.json()["country"] == "CO"

    resp = await client.post("/api/v1/policy/privacy/accept", headers=auth_headers(a))
    assert resp.status_code == 200, resp.text
    accepted = resp.json()
    assert accepted["country"] == "CO"
    assert accepted["version"]

    resp = await client.get("/api/v1/users/me", headers=auth_headers(a))
    assert resp.status_code == 200, resp.text
    assert resp.json()["needs_privacy_policy_acceptance"] is False
