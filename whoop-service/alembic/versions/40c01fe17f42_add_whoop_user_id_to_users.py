"""add whoop_user_id to users

Identifies the WHOOP account behind a user, so reconnecting updates the
existing row instead of creating a duplicate.

Revision ID: 40c01fe17f42
Revises: e4b7c1a9d2f0
Create Date: 2026-09-28 20:50:21.857972

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "40c01fe17f42"
down_revision: str | Sequence[str] | None = "e4b7c1a9d2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("whoop_user_id", sa.String(), nullable=True))
    op.create_unique_constraint("users_whoop_user_id_key", "users", ["whoop_user_id"])


def downgrade() -> None:
    op.drop_constraint("users_whoop_user_id_key", "users", type_="unique")
    op.drop_column("users", "whoop_user_id")
