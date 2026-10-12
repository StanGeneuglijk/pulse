"""One async engine and session factory per process."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    # Supabase's pooler (transaction mode) already pools: no app-side pool,
    # and no prepared-statement cache, which transaction pooling breaks.
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed automatically."""
    async with async_session_factory() as session:
        yield session
