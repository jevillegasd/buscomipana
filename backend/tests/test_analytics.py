import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.analytics import PingAnalyticsEvent
from app.models.enums import PingStatus
from app.services.analytics_service import compute_subject_hash
from tests.conftest import signup_and_login

PHONE_A = "+573008888881"
PHONE_B = "+573008888882"


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


@pytest.mark.asyncio
async def test_ping_is_anonymized_and_pong_latency_is_recorded(client, db_engine):
    a = await signup_and_login(client, PHONE_A)
    b = await signup_and_login(client, PHONE_B)

    resp = await client.post(
        "/api/v1/pings", json={"status": "distress"}, headers=auth_headers(a)
    )
    assert resp.status_code == 201, resp.text
    ping_id = resp.json()["id"]

    # Every signup also seeds an initial "ok" self-ping (see
    # auth_service.verify_login_otp), so there are more analytics rows than just
    # the explicit distress ping created above -- select on status to isolate it.
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(select(PingAnalyticsEvent).where(PingAnalyticsEvent.status == PingStatus.distress))
        events = result.scalars().all()
        assert len(events) == 1
        event = events[0]

        # Irreversibility: the raw subject id never appears in the analytics
        # row, and the hash cannot be recomputed without the pepper.
        assert a["user_id"] not in event.subject_hash
        assert event.subject_hash == compute_subject_hash(a["user_id"])
        assert event.subject_hash != compute_subject_hash(a["user_id"], pepper="wrong-pepper")
        assert event.status.value == "distress"
        assert event.is_proxy is False
        assert event.first_pong_latency_seconds is None

    resp = await client.post(
        f"/api/v1/pings/{ping_id}/pongs",
        json={"message": "on my way", "audience": "directed"},
        headers=auth_headers(b),
    )
    assert resp.status_code == 201, resp.text

    async with session_factory() as db:
        result = await db.execute(select(PingAnalyticsEvent).where(PingAnalyticsEvent.status == PingStatus.distress))
        event = result.scalars().one()
        assert event.first_pong_latency_seconds is not None
        assert event.first_pong_latency_seconds >= 0
