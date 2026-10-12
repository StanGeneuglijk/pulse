import pytest
import pytest_asyncio

from core.queue import redis_conn
from services.whoop import circuit_breaker
from services.whoop.config import WHOOP_CIRCUIT_THRESHOLD
from services.whoop.exceptions import WhoopDegradedError


class TestCircuitBreaker:
    @pytest_asyncio.fixture(autouse=True)
    async def _clean_state(self):
        await circuit_breaker.record_success()  # clears any leftover count
        yield
        await circuit_breaker.record_success()

    async def test_happy_path_closed_circuit_does_not_raise(self):
        await circuit_breaker.raise_if_open()  # no exception = still closed

    async def test_edge_case_trips_open_after_the_threshold_is_reached(self):
        for _ in range(WHOOP_CIRCUIT_THRESHOLD):
            await circuit_breaker.record_failure()

        with pytest.raises(WhoopDegradedError):
            await circuit_breaker.raise_if_open()

    async def test_edge_case_stays_closed_one_failure_short_of_the_threshold(self):
        for _ in range(WHOOP_CIRCUIT_THRESHOLD - 1):
            await circuit_breaker.record_failure()

        await circuit_breaker.raise_if_open()  # no exception

    async def test_happy_path_a_success_resets_the_count_even_after_failures(self):
        for _ in range(WHOOP_CIRCUIT_THRESHOLD - 1):
            await circuit_breaker.record_failure()

        await circuit_breaker.record_success()

        for _ in range(WHOOP_CIRCUIT_THRESHOLD - 1):
            await circuit_breaker.record_failure()
        await circuit_breaker.raise_if_open()  # still closed — success wiped the earlier count

    async def test_edge_case_a_tripped_circuit_names_the_failure_count(self):
        for _ in range(WHOOP_CIRCUIT_THRESHOLD):
            await circuit_breaker.record_failure()

        with pytest.raises(WhoopDegradedError) as exc_info:
            await circuit_breaker.raise_if_open()
        assert exc_info.value.consecutive_failures == WHOOP_CIRCUIT_THRESHOLD


def teardown_module() -> None:
    redis_conn.delete("whoop:circuit:consecutive_failures")
