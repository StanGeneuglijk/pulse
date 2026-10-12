"""drop request_logs and health_check_logs

Request and health-check logging moved to structured stdout — the rows
were ~90% health-check noise. See core/request_logging.py.

Revision ID: e4b7c1a9d2f0
Revises: c95fa9ad5f14
Create Date: 2026-09-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b7c1a9d2f0"
down_revision: str | Sequence[str] | None = "c95fa9ad5f14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("request_logs")
    op.drop_table("health_check_logs")


def downgrade() -> None:
    op.create_table(
        "health_check_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failed_dependency", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_check_logs_created_at", "health_check_logs", ["created_at"])
    op.create_table(
        "request_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("caller_type", sa.String(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_logs_created_at", "request_logs", ["created_at"])
