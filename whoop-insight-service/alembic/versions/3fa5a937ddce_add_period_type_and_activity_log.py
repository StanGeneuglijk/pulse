"""add period_type and activity log

Revision ID: 3fa5a937ddce
Revises: 81ded8f4838e
Create Date: 2026-09-27 15:23:26.618463

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3fa5a937ddce"
down_revision: str | Sequence[str] | None = "81ded8f4838e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "insight_activity_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_insight_activity_logs_created_at"),
        "insight_activity_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_insight_activity_logs_user_id", "insight_activity_logs", ["user_id"], unique=False
    )
    op.add_column("insight_job_logs", sa.Column("period_type", sa.String(), nullable=False))
    op.add_column("insights", sa.Column("period_type", sa.String(), nullable=False))
    op.drop_constraint(op.f("uq_user_insight_period"), "insights", type_="unique")
    op.create_unique_constraint(
        "uq_user_insight_period",
        "insights",
        ["user_id", "period_type", "period_start", "period_end", "prompt_version"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_user_insight_period", "insights", type_="unique")
    op.create_unique_constraint(
        op.f("uq_user_insight_period"),
        "insights",
        ["user_id", "period_start", "period_end", "prompt_version"],
    )
    op.drop_column("insights", "period_type")
    op.drop_column("insight_job_logs", "period_type")
    op.drop_index("ix_insight_activity_logs_user_id", table_name="insight_activity_logs")
    op.drop_index(op.f("ix_insight_activity_logs_created_at"), table_name="insight_activity_logs")
    op.drop_table("insight_activity_logs")
