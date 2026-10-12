"""enable RLS (zero policies) on every nutrition table

Revision ID: c3a1f0d2e7b4
Revises: bfb705270b50
Create Date: 2026-09-28 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3a1f0d2e7b4'
down_revision: str | Sequence[str] | None = 'bfb705270b50'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same reasoning as whoop-service's own c95fa9ad5f14: these tables live in
# the shared Supabase project's `public` schema, which Supabase's REST API
# exposes to its anon/authenticated roles. RLS with zero policies closes
# that door; this service's own connection (the table-owning postgres
# role) bypasses RLS, so it costs nothing here. Meal logs and chat history
# are personal health data, so every table is covered, logs included.
_TABLES = [
    "nutrition_conversations",
    "nutrition_messages",
    "nutrition_logs",
    "nutrition_meal_items",
    "nutrition_goals",
    "nutrition_job_logs",
    "nutrition_activity_logs",
    "nutrition_alembic_version",
]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
