import io

import pytest
from PIL import Image

from tests.conftest import signup_and_login

PHONE_A = "+573009990001"
PHONE_B = "+573009990002"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


def make_test_image_bytes(color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", (40, 40), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_profile_fields_roundtrip(client):
    a = await signup_and_login(client, PHONE_A)

    resp = await client.patch(
        "/api/v1/users/me",
        json={
            "full_name": "Camila Torres",
            "national_id_number": "1020304050",
            "birth_date": "1994-03-12",
            "residence_place": "Bogotá, Colombia",
            "nationality": "Colombiana",
            "distinguishable_gender": "female",
        },
        headers=auth_headers(a),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["national_id_number"] == "1020304050"
    assert body["birth_date"] == "1994-03-12"
    assert body["residence_place"] == "Bogotá, Colombia"
    assert body["nationality"] == "Colombiana"
    assert body["distinguishable_gender"] == "female"
    assert body["has_profile_photo"] is False


@pytest.mark.asyncio
async def test_national_id_number_gated_like_location(client):
    a = await signup_and_login(client, PHONE_A)
    b = await signup_and_login(client, PHONE_B)

    await client.patch(
        "/api/v1/users/me", json={"national_id_number": "999888777"}, headers=auth_headers(a)
    )

    # Stranger cannot see the national ID number.
    resp = await client.get(f"/api/v1/users/{a['user_id']}", headers=auth_headers(b))
    assert resp.status_code == 200
    assert resp.json()["national_id_number"] is None

    # After an accepted relative link, it becomes visible -- same trust
    # boundary as location.
    resp = await client.post(
        "/api/v1/relative-links", json={"target_phone_number": PHONE_A}, headers=auth_headers(b)
    )
    link_id = resp.json()["id"]
    await client.post(f"/api/v1/relative-links/{link_id}/accept", headers=auth_headers(a))

    resp = await client.get(f"/api/v1/users/{a['user_id']}", headers=auth_headers(b))
    assert resp.json()["national_id_number"] == "999888777"


@pytest.mark.asyncio
async def test_profile_photo_upload_visibility_and_delete(client):
    a = await signup_and_login(client, PHONE_A)
    b = await signup_and_login(client, PHONE_B)

    resp = await client.put(
        "/api/v1/users/me/profile-photo",
        files={"file": ("photo.png", make_test_image_bytes(), "image/png")},
        headers=auth_headers(a),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["has_profile_photo"] is True

    # Owner can always fetch their own photo.
    resp = await client.get(f"/api/v1/users/{a['user_id']}/profile-photo", headers=auth_headers(a))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"

    # Stranger cannot.
    resp = await client.get(f"/api/v1/users/{a['user_id']}/profile-photo", headers=auth_headers(b))
    assert resp.status_code == 404

    resp = await client.delete("/api/v1/users/me/profile-photo", headers=auth_headers(a))
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/users/{a['user_id']}/profile-photo", headers=auth_headers(a))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_photo_upload_rejects_non_image(client):
    a = await signup_and_login(client, PHONE_A)

    resp = await client.put(
        "/api/v1/users/me/profile-photo",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
        headers=auth_headers(a),
    )
    assert resp.status_code == 422
