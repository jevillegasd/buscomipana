import pytest

from tests.conftest import signup_and_login

PHONE_REPORTER = "+573004444001"
PHONE_UNCLAIMED = "+573004444002"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_report_for_unregistered_phone_resolves_when_that_person_later_signs_up(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)

    # Report filed before the subject has ever created an account.
    resp = await client.post(
        "/api/v1/missing-person-reports",
        json={"subject_full_name": "Lost Sibling", "subject_phone_number": PHONE_UNCLAIMED},
        headers=auth_headers(reporter),
    )
    assert resp.status_code == 201, resp.text
    report = resp.json()
    assert report["status"] == "open"
    assert report["matched_user_id"] is None

    # The subject shows up later and creates their account.
    subject = await signup_and_login(client, PHONE_UNCLAIMED)

    # Signing up itself seeds an initial "ok" ping.
    resp = await client.get("/api/v1/users/me/pings", headers=auth_headers(subject))
    assert resp.status_code == 200
    pings = resp.json()
    assert len(pings) == 1
    assert pings[0]["status"] == "ok"

    # The previously-open report is now auto-resolved against the new account.
    resp = await client.get(f"/api/v1/missing-person-reports/{report['id']}", headers=auth_headers(reporter))
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["status"] == "matched"
    assert updated["matched_user_id"] == subject["user_id"]
