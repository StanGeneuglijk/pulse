"""add operational and behavioral log tables

Revision ID: b10a4a52d90f
Revises: 760f3fa037eb
Create Date: 2026-08-19 21:30:36.220631

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b10a4a52d90f"
down_revision: str | Sequence[str] | None = "760f3fa037eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exception_type", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_error_logs_created_at"), "error_logs", ["created_at"], unique=False)
    op.create_table(
        "health_check_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failed_dependency", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_health_check_logs_created_at"),
        "health_check_logs",
        ["created_at"],
        unique=False,
    )
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
    op.create_index(
        op.f("ix_request_logs_created_at"), "request_logs", ["created_at"], unique=False
    )
    # user_id is a plain column, not a ForeignKey, on both log tables
    # below — see the model docstrings: a hard FK would reject logging
    # the exact case most worth logging (a sync attempt for a user_id
    # that doesn't exist at all).
    op.create_table(
        "sync_job_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("trigger_source", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("retries_left", sa.Integer(), nullable=True),
        sa.Column("recoveries_synced", sa.Integer(), nullable=False),
        sa.Column("sleep_synced", sa.Integer(), nullable=False),
        sa.Column("workouts_synced", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sync_job_logs_created_at"), "sync_job_logs", ["created_at"], unique=False
    )
    op.create_index("ix_sync_job_logs_user_id", "sync_job_logs", ["user_id"], unique=False)
    op.create_table(
        "user_activity_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_activity_logs_created_at"),
        "user_activity_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_activity_logs_user_id", "user_activity_logs", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_user_activity_logs_user_id", table_name="user_activity_logs")
    op.drop_index(op.f("ix_user_activity_logs_created_at"), table_name="user_activity_logs")
    op.drop_table("user_activity_logs")
    op.drop_index("ix_sync_job_logs_user_id", table_name="sync_job_logs")
    op.drop_index(op.f("ix_sync_job_logs_created_at"), table_name="sync_job_logs")
    op.drop_table("sync_job_logs")
    op.drop_index(op.f("ix_request_logs_created_at"), table_name="request_logs")
    op.drop_table("request_logs")
    op.drop_index(op.f("ix_health_check_logs_created_at"), table_name="health_check_logs")
    op.drop_table("health_check_logs")
    op.drop_index(op.f("ix_error_logs_created_at"), table_name="error_logs")
    op.drop_table("error_logs")
