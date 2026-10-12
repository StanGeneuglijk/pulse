"""Alembic environment. `db_url` is kept as a plain Python variable, never
round-tripped through configparser's set_main_option/get_main_option — a
password containing a literal "%" (e.g. a percent-encoded "%23") collides
with configparser's own interpolation syntax and raises ValueError.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from core import log_models  # noqa: F401 — import so Base.metadata sees every table
from core.config import settings
from core.db import Base
from services.whoop import models  # noqa: F401 — import so Base.metadata sees every table

config = context.config
db_url = settings.database_url_direct or settings.database_url

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = db_url
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
