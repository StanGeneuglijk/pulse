"""add insight job logs

Revision ID: 81ded8f4838e
Revises: 6f45f9f141f7
Create Date: 2026-09-27 14:29:24.723518

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81ded8f4838e"
down_revision: str | Sequence[str] | None = "6f45f9f141f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "insight_job_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Double(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_insight_job_logs_created_at"), "insight_job_logs", ["created_at"], unique=False
    )
    op.create_index("ix_insight_job_logs_user_id", "insight_job_logs", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_insight_job_logs_user_id", table_name="insight_job_logs")
    op.drop_index(op.f("ix_insight_job_logs_created_at"), table_name="insight_job_logs")
    op.drop_table("insight_job_logs")
