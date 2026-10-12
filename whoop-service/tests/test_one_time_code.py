from core.one_time_code import OneTimeCodeStore
from core.queue import redis_conn
from services.whoop.config import EXCHANGE_CODE_KEY_PREFIX, EXCHANGE_CODE_TTL_SECONDS


class TestOneTimeCodeStore:
    def setup_method(self) -> None:
        self.store = OneTimeCodeStore(EXCHANGE_CODE_KEY_PREFIX, EXCHANGE_CODE_TTL_SECONDS)

    def teardown_method(self) -> None:
        for key in redis_conn.scan_iter(f"{EXCHANGE_CODE_KEY_PREFIX}*"):
            redis_conn.delete(key)

    async def test_happy_path_round_trips_the_payload(self):
        code = await self.store.create({"user_id": "abc", "read_token": "xyz"})

        assert await self.store.consume(code) == {"user_id": "abc", "read_token": "xyz"}

    async def test_edge_case_a_code_can_only_be_consumed_once(self):
        """Scope: replay protection — the same property OAuthStateStore
        gives a bare presence check, here extended to carry data."""
        code = await self.store.create({"user_id": "abc", "read_token": "xyz"})
        await self.store.consume(code)

        assert await self.store.consume(code) is None

    async def test_edge_case_an_unknown_code_returns_none(self):
        assert await self.store.consume("never-issued") is None
