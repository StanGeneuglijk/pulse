"""workouts score is a decimal strain value, not an integer

Revision ID: 760f3fa037eb
Revises: c12d3d6c2366
Create Date: 2026-08-18 22:33:00.940916

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "760f3fa037eb"
down_revision: str | Sequence[str] | None = "c12d3d6c2366"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("workouts", "score", existing_type=sa.Integer(), type_=sa.Float())


def downgrade() -> None:
    op.alter_column("workouts", "score", existing_type=sa.Float(), type_=sa.Integer())
