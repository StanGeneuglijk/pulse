"""Runnable, non-pytest showcase: a plain CLI chat loop against whatever
`DATABASE_URL`/`REDIS_URL`/`ANTHROPIC_API_KEY` this service's `.env`
currently points at — local dev infra or the real Supabase/Upstash
instance, unchanged either way. Makes real, billed Anthropic calls; the
spend cap (`NUTRITION_SPEND_LIMIT_USD`) still applies. Mirrors
whoop-insight-service's own scripts/run_insight_example.py.

Usage (from whoop-nutrition-service/):
    uv run python scripts/run_chat_example.py --user-id <uuid>

Type a message and press enter. When Claude proposes a breakdown, you'll
be asked to confirm or discard it. Ctrl-C to quit.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Run as a plain script, not `python -m` — see whoop-insight-service's
# own run_insight_example.py for why this shim is needed here too.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import async_session_factory  # noqa: E402
from services.nutrition.chat import handle_turn  # noqa: E402
from services.nutrition.crud import confirm_meal, discard_pending_meal  # noqa: E402
from services.nutrition.exceptions import DomainError  # noqa: E402
from services.nutrition.providers import get_llm_client  # noqa: E402


async def main(user_id: uuid.UUID) -> int:
    conversation_id: uuid.UUID | None = None
    llm_client = get_llm_client()

    print("Describe a meal (Ctrl-C to quit).\n")
    while True:
        try:
            # input() blocks — run_in_threadpool-equivalent for a plain
            # script, same "never a bare blocking call inside async def"
            # rule the rest of this platform holds itself to.
            message = (await asyncio.to_thread(input, "you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue

        async with async_session_factory() as db:
            try:
                conversation, reply, pending = await handle_turn(
                    db, llm_client, user_id, conversation_id, message
                )
            except DomainError as exc:
                print(f"  ! {exc}", file=sys.stderr)
                continue

            conversation_id = conversation.id
            if reply:
                print(f"assistant> {reply}")

            if pending is not None:
                print(f"\n  Proposed: {pending.description}")
                for item in pending.items:
                    print(f"    - {item.name} ({item.quantity}): {item.calories} kcal")
                print(
                    f"  Total: {pending.total_calories} kcal, "
                    f"{pending.total_protein_g:.0f}g protein, "
                    f"{pending.total_carbs_g:.0f}g carbs, {pending.total_fat_g:.0f}g fat"
                )
                choice = (await asyncio.to_thread(input, "  confirm? [y/N] ")).strip().lower()
                if choice == "y":
                    log = await confirm_meal(db, conversation.id)
                    print(f"  Saved as {log.id}\n")
                else:
                    await discard_pending_meal(db, conversation.id)
                    print("  Discarded.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=uuid.UUID)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.user_id)))
