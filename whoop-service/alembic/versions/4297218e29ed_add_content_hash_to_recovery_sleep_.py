"""add content_hash to recovery, sleep, workout

Revision ID: 4297218e29ed
Revises: dac551357c8a
Create Date: 2026-08-17 21:29:50.322048

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4297218e29ed"
down_revision: str | Sequence[str] | None = "dac551357c8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default="" rather than a nullable column: any pre-existing row
    # gets a hash that can never match a freshly computed one, so the next
    # sync always treats it as changed and writes a real hash — self-healing,
    # no backfill script needed.
    op.add_column(
        "recoveries", sa.Column("content_hash", sa.String(), nullable=False, server_default="")
    )
    op.add_column(
        "sleeps", sa.Column("content_hash", sa.String(), nullable=False, server_default="")
    )
    op.add_column(
        "workouts", sa.Column("content_hash", sa.String(), nullable=False, server_default="")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workouts", "content_hash")
    op.drop_column("sleeps", "content_hash")
    op.drop_column("recoveries", "content_hash")
