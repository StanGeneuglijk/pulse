"""enable RLS (zero policies) on users, recoveries, sleeps, workouts,
alembic_version

Revision ID: c95fa9ad5f14
Revises: ef8083512090
Create Date: 2026-09-11 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c95fa9ad5f14"
down_revision: str | Sequence[str] | None = "ef8083512090"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# RLS with zero policies only affects the anon/authenticated roles
# Supabase's client SDK/REST API would use — this service's own
# connection (DATABASE_URL, authenticated as the postgres role) bypasses
# RLS as table owner, so this costs nothing here while closing an
# otherwise-open door for a key (the publishable key) this service
# doesn't currently expose anywhere, but could in the future. Scoped to
# exactly the tables the hosting docs list
# as covered; the five operational/behavioral log tables predate that
# doc's RLS claim and aren't included here.
_TABLES = ["users", "recoveries", "sleeps", "workouts", "alembic_version"]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
