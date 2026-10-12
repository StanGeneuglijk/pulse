import dataclasses
import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://nutrition:nutrition@localhost:5434/nutrition_platform_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6381")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("OPENAI_API_KEY", "")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import core.health
from api.main import app
from core.clock import utcnow
from core.db import Base, async_session_factory, engine
from services.nutrition.auth import _metadata as auth_users_metadata
from services.nutrition.auth import users as auth_users_table
from services.nutrition.llm import ChatResult, MealItemProposal, MealProposal
from services.nutrition.providers import get_llm_client, get_transcription_client
from services.nutrition.transcription import TranscriptionResult

AUTH_HEADERS = {"Authorization": f"Bearer {os.environ['API_KEY']}"}



@pytest.fixture(autouse=True)
def _no_cached_redis_ping(monkeypatch):
    """/health reuses a recent successful Redis ping (core/health.py); every
    test starts without one, so a check in one test can't mask another's."""
    monkeypatch.setattr(core.health, "_redis_ok_at", None)

@pytest_asyncio.fixture
async def db_session():
    """Creates only whoop-nutrition-service's own tables — proves
    task 4's acceptance that Base.metadata never reaches into another
    service's schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def users_table(db_session):
    """A local stand-in for whoop-service's own `users` table — just the
    `id`/`read_token` columns services/nutrition/auth.py reads
    read-only."""
    async with engine.begin() as conn:
        await conn.run_sync(auth_users_metadata.create_all)
    yield
    await db_session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(auth_users_metadata.drop_all)


async def seed_read_token(db_session, user_id, read_token: str) -> None:
    await db_session.execute(auth_users_table.insert().values(id=user_id, read_token=read_token))
    await db_session.commit()


class FakeChatLLMClient:
    """A stand-in ChatLLMClient — never imports `anthropic`, proving
    chat.py depends only on the protocol."""

    def __init__(self, *, text: str | None = None, tool_call: MealProposal | None = None) -> None:
        self.text = text
        self.tool_call = tool_call
        self.calls = 0
        self.last_max_tokens: int | None = None
        self.last_effort: str | None = None

    async def send(self, *, system, messages, max_tokens, effort) -> ChatResult:
        self.calls += 1
        self.last_max_tokens = max_tokens
        self.last_effort = effort
        return ChatResult(
            text=self.text,
            tool_call=self.tool_call,
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def sample_meal_proposal(**overrides) -> MealProposal:
    base = MealProposal(
        description="Grilled chicken with rice",
        # "now", not a fixed date — summarize()'s window is computed
        # against the real utcnow() at test-run time, so a hardcoded
        # historical date would silently fall outside a "daily" window
        # on any day other than the one it was written on.
        logged_at=utcnow().isoformat(),
        items=[
            MealItemProposal(
                name="grilled chicken breast",
                quantity="150g",
                calories=250,
                protein_g=45.0,
                carbs_g=0.0,
                fat_g=6.0,
            ),
            MealItemProposal(
                name="white rice",
                quantity="1 cup",
                calories=200,
                protein_g=4.0,
                carbs_g=44.0,
                fat_g=0.5,
            ),
        ],
        total_calories=450,
        total_protein_g=49.0,
        total_carbs_g=44.0,
        total_fat_g=6.5,
    )
    return dataclasses.replace(base, **overrides) if overrides else base


class FakeTranscriptionClient:
    def __init__(
        self,
        *,
        text: str = "I had two eggs and toast",
        duration_seconds: float = 3.0,
        raises: Exception | None = None,
    ):
        self.text = text
        self.duration_seconds = duration_seconds
        self.raises = raises
        self.calls = 0

    async def transcribe(self, *, audio_bytes: bytes, content_type: str) -> TranscriptionResult:
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return TranscriptionResult(text=self.text, duration_seconds=self.duration_seconds)


@pytest_asyncio.fixture
def fake_llm_client():
    fake = FakeChatLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    del app.dependency_overrides[get_llm_client]


@pytest_asyncio.fixture
def fake_transcription_client():
    fake = FakeTranscriptionClient()
    app.dependency_overrides[get_transcription_client] = lambda: fake
    yield fake
    del app.dependency_overrides[get_transcription_client]


@pytest_asyncio.fixture
async def client(fake_llm_client, fake_transcription_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as ac:
        yield ac


@pytest_asyncio.fixture
async def anonymous_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
