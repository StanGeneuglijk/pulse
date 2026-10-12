import os
import uuid
from datetime import datetime

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://insight:insight@localhost:5433/insight_platform_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import core.health
from api.main import app
from core.clock import utcnow
from core.db import Base, async_session_factory, engine
from services.insight.auth import _metadata as auth_users_metadata
from services.insight.auth import users as auth_users_table
from services.insight.llm import LLMResult
from services.insight.nutrition_read import _metadata as nutrition_metadata
from services.insight.nutrition_read import nutrition_goals, nutrition_logs
from services.insight.providers import get_llm_client
from services.insight.whoop_read import _metadata as whoop_metadata
from services.insight.whoop_read import recoveries, sleeps, workouts

AUTH_HEADERS = {"Authorization": f"Bearer {os.environ['API_KEY']}"}



@pytest.fixture(autouse=True)
def _no_cached_redis_ping(monkeypatch):
    """/health reuses a recent successful Redis ping (core/health.py); every
    test starts without one, so a check in one test can't mask another's."""
    monkeypatch.setattr(core.health, "_redis_ok_at", None)

@pytest_asyncio.fixture
async def db_session():
    """Creates only whoop-insight-service's own tables (insights,
    insight_job_logs) — proves task 4/8's Base.metadata never touches
    whoop-service's tables, same assertion tasks.md's acceptance
    criteria make explicit."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def whoop_tables(db_session):
    """A local stand-in for whoop-service's recoveries/sleeps/workouts
    tables AND whoop-nutrition-service's nutrition_logs/nutrition_goals
    tables — generate_insight reads both unconditionally now (the
    nutrition ones are an *optional* additional source, but the read
    itself always happens, so the tables must always exist in tests),
    seeded directly via Core inserts — no dependency on either service's
    own code, just their schema shapes."""
    async with engine.begin() as conn:
        await conn.run_sync(whoop_metadata.create_all)
        await conn.run_sync(nutrition_metadata.create_all)
    yield
    # A test that only reads (fetch_window, with no follow-up commit)
    # leaves db_session idle-in-transaction, holding a lock this
    # fixture's own DROP TABLE then waits on forever — db_session's
    # teardown (which would close it) runs *after* this one, since
    # fixture teardown is reverse-of-setup order. Roll it back
    # explicitly first, rather than deadlock against it.
    await db_session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(whoop_metadata.drop_all)
        await conn.run_sync(nutrition_metadata.drop_all)


@pytest_asyncio.fixture
async def users_table(db_session):
    """A local stand-in for whoop-service's own `users` table — just the
    `id`/`read_token` columns services/insight/auth.py reads read-only.
    Separate from `whoop_tables` since only auth tests need this one."""
    async with engine.begin() as conn:
        await conn.run_sync(auth_users_metadata.create_all)
    yield
    await db_session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(auth_users_metadata.drop_all)


async def seed_read_token(db_session, user_id: uuid.UUID, read_token: str) -> None:
    await db_session.execute(
        auth_users_table.insert().values(id=user_id, read_token=read_token)
    )
    await db_session.commit()


async def seed_recovery(db_session, user_id: uuid.UUID, score: int, recorded_at: datetime) -> None:
    await db_session.execute(
        recoveries.insert().values(user_id=user_id, score=score, recorded_at=recorded_at)
    )
    await db_session.commit()


async def seed_sleep(db_session, user_id: uuid.UUID, score: int, recorded_at: datetime) -> None:
    await db_session.execute(
        sleeps.insert().values(user_id=user_id, score=score, recorded_at=recorded_at)
    )
    await db_session.commit()


async def seed_workout(db_session, user_id: uuid.UUID, score: float, recorded_at: datetime) -> None:
    await db_session.execute(
        workouts.insert().values(user_id=user_id, score=score, recorded_at=recorded_at)
    )
    await db_session.commit()


async def seed_nutrition_log(
    db_session,
    user_id: uuid.UUID,
    *,
    calories: int,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    logged_at: datetime,
) -> None:
    await db_session.execute(
        nutrition_logs.insert().values(
            user_id=user_id,
            calories=calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            logged_at=logged_at,
        )
    )
    await db_session.commit()


async def seed_goal(
    db_session,
    user_id: uuid.UUID,
    *,
    goal_type: str,
    target_calories: int | None = None,
    target_protein_g: float | None = None,
) -> None:
    await db_session.execute(
        nutrition_goals.insert().values(
            user_id=user_id,
            goal_type=goal_type,
            target_calories=target_calories,
            target_protein_g=target_protein_g,
            target_carbs_g=None,
            target_fat_g=None,
            is_active=True,
            created_at=utcnow(),
        )
    )
    await db_session.commit()


class FakeLLMClient:
    """A stand-in LLMClient — never imports `anthropic`, proving
    generate.py depends only on the protocol (task 2's acceptance)."""

    def __init__(self, *, text: str = "You've been recovering well this week.") -> None:
        self.text = text
        self.calls = 0
        self.last_max_tokens: int | None = None
        self.last_effort: str | None = None
        self.last_user_prompt: str | None = None

    async def generate(
        self, *, system: str, user_prompt: str, max_tokens: int, effort: str
    ) -> LLMResult:
        self.calls += 1
        self.last_max_tokens = max_tokens
        self.last_effort = effort
        self.last_user_prompt = user_prompt
        return LLMResult(text=self.text, model="fake-model", input_tokens=10, output_tokens=5)


@pytest_asyncio.fixture
def fake_llm_client():
    """Overrides the real Anthropic-backed dependency with a fake one for
    the duration of one test — no test in this suite makes a real,
    billed LLM call."""
    fake = FakeLLMClient()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    del app.dependency_overrides[get_llm_client]


@pytest_asyncio.fixture
async def client(fake_llm_client):
    """An HTTP client carrying the operator API_KEY, with the LLM call
    faked out."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as ac:
        yield ac


@pytest_asyncio.fixture
async def anonymous_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
