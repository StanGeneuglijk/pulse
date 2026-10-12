from core.locks import acquire_lock
from core.queue import redis_conn
from services.whoop.config import BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS


class TestAcquireBatchLock:
    def setup_method(self) -> None:
        redis_conn.delete(BATCH_LOCK_KEY)

    def teardown_method(self) -> None:
        redis_conn.delete(BATCH_LOCK_KEY)

    async def test_happy_path_the_first_caller_wins(self):
        assert await acquire_lock(BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS) is True

    async def test_edge_case_a_second_caller_within_the_window_loses(self):
        assert await acquire_lock(BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS) is True
        assert await acquire_lock(BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS) is False

    async def test_edge_case_a_call_after_the_lock_expires_wins_again(self):
        """Scope: this isn't a permanent lock — once the TTL is gone
        (simulated here by clearing the key directly, the same end
        state a real expiry produces, without a real 5-minute wait),
        a later call must be able to win again."""
        assert await acquire_lock(BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS) is True
        redis_conn.delete(BATCH_LOCK_KEY)  # simulates BATCH_LOCK_TTL_SECONDS elapsing

        assert await acquire_lock(BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS) is True
