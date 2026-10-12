"""add read_token to users

Revision ID: c12d3d6c2366
Revises: 4297218e29ed
Create Date: 2026-08-17 22:12:35.975906

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c12d3d6c2366"
down_revision: str | Sequence[str] | None = "4297218e29ed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable, no backfill: read_token is only ever set when a user row is
    # first created (services/whoop/crud.py's create_or_update_user), so an
    # existing pre-migration user has none until they reconnect via OAuth —
    # until then, only the master API_KEY can read their data.
    op.add_column("users", sa.Column("read_token", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_read_token", "users", ["read_token"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_users_read_token", "users", type_="unique")
    op.drop_column("users", "read_token")
