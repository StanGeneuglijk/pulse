"""Runnable, non-pytest showcase: generates one real insight end to end
against whatever `DATABASE_URL`/`REDIS_URL`/`ANTHROPIC_API_KEY` this
service's `.env` currently points at — local dev infra or the real
Supabase/Upstash instance, unchanged either way. Makes one real,
billed Anthropic API call; the spend cap (`INSIGHT_SPEND_LIMIT_USD`)
still applies and will refuse to run past it, same as the API would.

Usage (from whoop-insight-service/):
    uv run python scripts/run_insight_example.py --user-id <uuid>
    uv run python scripts/run_insight_example.py --user-id <uuid> --period monthly

`--user-id` must already have synced WHOOP data in the connected
database — this script only generates from data that's already there,
it doesn't sync anything itself (that's whoop-service's job).
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Run as a plain script (`python scripts/run_insight_example.py`), not
# `python -m` — sys.path[0] is this file's own directory, not the
# project root every other entrypoint (uvicorn, alembic, pytest) runs
# from. Insert the root explicitly so `core`/`services` resolve the
# same way they do everywhere else in this service.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import async_session_factory  # noqa: E402
from services.insight.config import INSIGHT_SPEND_LIMIT_USD, InsightPeriod  # noqa: E402
from services.insight.crud import total_spend_usd  # noqa: E402
from services.insight.exceptions import DomainError  # noqa: E402
from services.insight.generate import generate_insight  # noqa: E402
from services.insight.providers import get_llm_client  # noqa: E402


async def main(user_id: uuid.UUID, period: InsightPeriod) -> int:
    async with async_session_factory() as db:
        llm_client = get_llm_client()
        try:
            insight = await generate_insight(db, llm_client, user_id, period)
        except DomainError as exc:
            print(f"Generation failed: {exc}", file=sys.stderr)
            return 1

        spent = await total_spend_usd(db)

    print(f"\n--- {period} insight for {user_id} ---")
    print(f"Model:  {insight.model_name}")
    print(f"Period: {insight.period_start.date()} -> {insight.period_end.date()}")
    print(f"\n{insight.content}\n")
    print(f"Cumulative spend so far: ${spent:.4f} / ${INSIGHT_SPEND_LIMIT_USD:.2f} cap")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=uuid.UUID)
    parser.add_argument(
        "--period", default="weekly", choices=["daily", "weekly", "monthly"]
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.user_id, args.period)))
