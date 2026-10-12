import os
import secrets
import uuid
from datetime import timedelta

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://whoop:whoop@localhost:5432/whoop_platform_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHOOP_CLIENT_ID", "test")
os.environ.setdefault("WHOOP_CLIENT_SECRET", "test")
os.environ.setdefault("WHOOP_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "q1D3_xXbvnPRBJsZmexB22Gr9Fiqkwb74KQlwsDNaEA=")
os.environ.setdefault("API_KEY", "test-api-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import core.health
from api.main import app
from core.clock import utcnow
from core.crypto import encrypt_token
from core.db import Base, async_session_factory, engine
from services.whoop.config import sync_queue
from services.whoop.models import User
from tests.support import WorkerHarness

AUTH_HEADERS = {"Authorization": f"Bearer {os.environ['API_KEY']}"}


@pytest.fixture(autouse=True)
def _no_cached_redis_ping(monkeypatch):
    """/health reuses a recent successful Redis ping (core/health.py); every
    test starts without one, so a check in one test can't mask another's."""
    monkeypatch.setattr(core.health, "_redis_ok_at", None)


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def connected_user(db_session):
    from core.config import settings

    user = User(
        id=uuid.uuid4(),
        encrypted_access_token=encrypt_token("fake-access-token", settings.token_encryption_key),
        encrypted_refresh_token=encrypt_token("fake-refresh-token", settings.token_encryption_key),
        token_expires_at=utcnow() + timedelta(hours=1),
        whoop_connected=True,
        read_token=secrets.token_urlsafe(32),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def expired_user(db_session):
    from core.config import settings

    user = User(
        id=uuid.uuid4(),
        encrypted_access_token=encrypt_token("stale-access-token", settings.token_encryption_key),
        encrypted_refresh_token=encrypt_token("valid-refresh-token", settings.token_encryption_key),
        token_expires_at=utcnow() - timedelta(minutes=1),  # already expired
        whoop_connected=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client():
    """An HTTP client carrying the operator API_KEY — the common case for
    exercising a protected route. See anonymous_client for the rejection
    case."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as ac:
        yield ac


@pytest_asyncio.fixture
async def anonymous_client():
    """An HTTP client with no Authorization header at all — for proving a
    protected route actually rejects an unauthenticated caller."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
def worker_harness():
    """A real RQ worker (see tests/support.py), with the queue guaranteed
    empty before and after — every worker-integration test starts from
    and returns to a clean queue."""
    sync_queue.empty()
    yield WorkerHarness()
    sync_queue.empty()
