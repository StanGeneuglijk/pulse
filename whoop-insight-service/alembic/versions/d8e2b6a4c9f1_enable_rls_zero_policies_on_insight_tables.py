"""enable RLS (zero policies) on every insight table

Revision ID: d8e2b6a4c9f1
Revises: 3fa5a937ddce
Create Date: 2026-09-28 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e2b6a4c9f1"
down_revision: str | Sequence[str] | None = "3fa5a937ddce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same reasoning as whoop-service's own c95fa9ad5f14: these tables live in
# the shared Supabase project's `public` schema, which Supabase's REST API
# exposes to its anon/authenticated roles. RLS with zero policies closes
# that door; this service's own connection (the table-owning postgres
# role) bypasses RLS, so it costs nothing here. Generated insights
# summarize personal health data, so every table is covered, logs included.
_TABLES = [
    "insights",
    "insight_job_logs",
    "insight_activity_logs",
    "insight_alembic_version",
]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
