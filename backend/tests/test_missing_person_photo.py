import io

import pytest
from PIL import Image

from tests.conftest import signup_and_login

PHONE_REPORTER = "+573009991001"
PHONE_OTHER = "+573009991002"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


def make_test_image_bytes() -> bytes:
    img = Image.new("RGB", (40, 40), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def _create_report(client, reporter_token):
    resp = await client.post(
        "/api/v1/missing-person-reports",
        json={
            "subject_full_name": "Persona Desaparecida",
            "subject_phone_number": "+573009999999",
            "missing_since": "2026-08-01",
            "missing_location_description": "Cerca al parque central",
            "last_known_clothing": "Camisa roja",
            "body_marks": "Cicatriz en la ceja izquierda",
        },
        headers=auth_headers(reporter_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_report_new_fields_roundtrip(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)
    report = await _create_report(client, reporter)

    assert report["missing_since"] == "2026-08-01"
    assert report["missing_location_description"] == "Cerca al parque central"
    assert report["last_known_clothing"] == "Camisa roja"
    assert report["body_marks"] == "Cicatriz en la ceja izquierda"
    assert report["has_photo"] is False


@pytest.mark.asyncio
async def test_photo_upload_requires_both_consents(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)
    report = await _create_report(client, reporter)

    # Missing AI-processing consent -> rejected.
    resp = await client.put(
        f"/api/v1/missing-person-reports/{report['id']}/photo",
        files={"file": ("photo.jpg", make_test_image_bytes(), "image/jpeg")},
        data={"consent_public_use": "true", "consent_ai_processing": "false"},
        headers=auth_headers(reporter),
    )
    assert resp.status_code == 422, resp.text

    resp = await client.get(f"/api/v1/missing-person-reports/{report['id']}", headers=auth_headers(reporter))
    assert resp.json()["has_photo"] is False


@pytest.mark.asyncio
async def test_photo_upload_with_consent_is_publicly_visible_to_any_authenticated_user(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)
    other = await signup_and_login(client, PHONE_OTHER)
    report = await _create_report(client, reporter)

    resp = await client.put(
        f"/api/v1/missing-person-reports/{report['id']}/photo",
        files={"file": ("photo.jpg", make_test_image_bytes(), "image/jpeg")},
        data={"consent_public_use": "true", "consent_ai_processing": "true"},
        headers=auth_headers(reporter),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["has_photo"] is True

    # Unrelated authenticated user can view it -- intentionally not gated like
    # the profile photo, matching the report's own open visibility and the
    # public-use consent just given.
    resp = await client.get(f"/api/v1/missing-person-reports/{report['id']}/photo", headers=auth_headers(other))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_only_reporter_can_upload_photo(client):
    reporter = await signup_and_login(client, PHONE_REPORTER)
    other = await signup_and_login(client, PHONE_OTHER)
    report = await _create_report(client, reporter)

    resp = await client.put(
        f"/api/v1/missing-person-reports/{report['id']}/photo",
        files={"file": ("photo.jpg", make_test_image_bytes(), "image/jpeg")},
        data={"consent_public_use": "true", "consent_ai_processing": "true"},
        headers=auth_headers(other),
    )
    assert resp.status_code == 403
