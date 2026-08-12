import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.limiter import limiter
from app.main import app
from app.models.analytics import PingAnalyticsEvent
from app.models.media import MediaAsset
from app.models.missing_person_report import (
    MissingPersonMatchCandidate,
    MissingPersonReport,
)
from app.models.otp import AuthSession, OtpVerification, TrustedDevice
from app.models.ping import Ping, Pong
from app.models.policy_acceptance import PolicyAcceptance
from app.models.relative_link import RelativeLink, ResponderCredential
from app.models.sms import InboundSmsMessage, SmsOutboxEntry
from app.models.user import User
from app.services import media_asset_service
from app.storage.local_storage import LocalDiskStorage

UNIT_TEST_TABLES = [
    User.__table__,
    OtpVerification.__table__,
    AuthSession.__table__,
    TrustedDevice.__table__,
    RelativeLink.__table__,
    ResponderCredential.__table__,
    Ping.__table__,
    Pong.__table__,
    SmsOutboxEntry.__table__,
    MissingPersonReport.__table__,
    MissingPersonMatchCandidate.__table__,
    InboundSmsMessage.__table__,
    PingAnalyticsEvent.__table__,
    MediaAsset.__table__,
    PolicyAcceptance.__table__,
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # The limiter's in-memory storage is process-global, so without a reset
    # requests from earlier tests count against later tests' rate limits (every
    # test client shares "127.0.0.1" as its key).
    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _isolated_media_storage(tmp_path, monkeypatch):
    # get_storage() is lru_cache'd and defaults to ./media -- without this,
    # every test run would write real files into the repo. media_asset_service
    # imported the name directly (from ... import get_storage), so it must be
    # patched there, not on app.storage.factory.
    storage = LocalDiskStorage(str(tmp_path / "media"))
    monkeypatch.setattr(media_asset_service, "get_storage", lambda: storage)
    yield


@pytest_asyncio.fixture
async def db_engine():
    # In-memory SQLite stands in for Postgres in unit tests that don't touch
    # Postgres-only features (JSONB, trigram/levenshtein extensions). Those paths
    # are covered separately against a real Postgres instance (see
    # docs/architecture.md verification section).
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=UNIT_TEST_TABLES)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def signup_and_login(client, phone_number: str) -> dict:
    from app.gateways.mock_gateway import get_last_sent_message

    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_number})
    assert resp.status_code == 202
    message = get_last_sent_message(phone_number)
    code = "".join(ch for ch in message if ch.isdigit())[-6:]
    resp = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone_number, "code": code})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    body["user_id"] = resp.json()["id"]
    return body
