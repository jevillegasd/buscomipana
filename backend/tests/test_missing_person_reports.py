import pytest

from tests.conftest import signup_and_login

PHONE_REPORTER = "+573005555555"
PHONE_MISSING = "+573006666666"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_exact_phone_match_resolves_report_immediately(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)
    missing = await signup_and_login(client, PHONE_MISSING)

    resp = await client.post(
        "/api/v1/missing-person-reports",
        json={"subject_full_name": "Maria Lopez", "subject_phone_number": PHONE_MISSING},
        headers=auth_headers(reporter),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "matched"
    assert body["matched_user_id"] == missing["user_id"]

    resp = await client.get("/api/v1/missing-person-reports", headers=auth_headers(reporter))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_no_match_stays_open_and_fuzzy_search_is_a_noop_on_sqlite(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)

    resp = await client.post(
        "/api/v1/missing-person-reports",
        json={"subject_full_name": "Unknown Person", "subject_phone_number": "+573009999999"},
        headers=auth_headers(reporter),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "open"
    assert body["matched_user_id"] is None

    resp = await client.get(
        f"/api/v1/missing-person-reports/{body['id']}/candidates", headers=auth_headers(reporter)
    )
    assert resp.status_code == 200
    assert resp.json() == []
