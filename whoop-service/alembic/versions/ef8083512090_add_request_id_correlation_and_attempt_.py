"""add request_id correlation and attempt_number to sync_job_logs

Revision ID: ef8083512090
Revises: b10a4a52d90f
Create Date: 2026-08-19 22:00:19.889394

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ef8083512090"
down_revision: str | Sequence[str] | None = "b10a4a52d90f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("error_logs", sa.Column("request_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_error_logs_request_id"), "error_logs", ["request_id"], unique=False)
    op.add_column("sync_job_logs", sa.Column("request_id", sa.Uuid(), nullable=True))
    # server_default only to backfill any existing rows safely; dropped
    # right after so new rows must supply a real value going forward.
    op.add_column(
        "sync_job_logs",
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("sync_job_logs", "attempt_number", server_default=None)
    op.create_index(
        op.f("ix_sync_job_logs_request_id"), "sync_job_logs", ["request_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_job_logs_request_id"), table_name="sync_job_logs")
    op.drop_column("sync_job_logs", "attempt_number")
    op.drop_column("sync_job_logs", "request_id")
    op.drop_index(op.f("ix_error_logs_request_id"), table_name="error_logs")
    op.drop_column("error_logs", "request_id")
