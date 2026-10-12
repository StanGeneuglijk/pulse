import core.health


class TestHealth:
    async def test_happy_path_ok_when_both_dependencies_are_reachable(self, anonymous_client):
        """Scope: the ordinary case — both Postgres and Redis reachable."""
        response = await anonymous_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_edge_case_503_when_postgres_is_unreachable(self, anonymous_client, monkeypatch):
        """Scope: /health claims to check both dependencies, not just
        Redis — this proves the Postgres half of that claim
        independently."""

        def _broken_connect(self, *args, **kwargs):
            raise ConnectionError("database is down")

        # AsyncEngine.connect is a read-only instance attribute — patch
        # the class instead, scoped back automatically when the test ends.
        monkeypatch.setattr(type(core.health.engine), "connect", _broken_connect)

        response = await anonymous_client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert "database" in body["detail"]

    async def test_edge_case_503_when_redis_is_unreachable(self, anonymous_client, monkeypatch):
        """Scope: the Redis half of the same claim — checked
        independently of Postgres, since either one being down must be
        reported on its own."""

        class _BrokenConn:
            async def ping(self) -> bool:
                raise ConnectionError("redis is down")

            async def __aenter__(self) -> "_BrokenConn":
                return self

            async def __aexit__(self, *exc_info) -> None:
                return None

        # get_redis_conn() builds a fresh connection per call (see its
        # own docstring for why) — patch the factory itself, since
        # there's no longer a single persistent instance to patch a
        # method on.
        monkeypatch.setattr(core.health, "get_redis_conn", lambda: _BrokenConn())

        response = await anonymous_client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert "redis" in body["detail"]


class _BrokenRedis:
    async def ping(self) -> bool:
        raise ConnectionError("redis is down")

    async def __aenter__(self) -> "_BrokenRedis":
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None


class TestHealthRedisBudget:
    """Render polls /health every ~10 s per service; a Redis ping each time
    used ~100K Upstash commands a day against a 500K/month free plan."""

    async def test_happy_path_reuses_a_recent_successful_ping(self, anonymous_client, monkeypatch):
        """Scope: within the TTL a second check doesn't touch Redis at all."""
        assert (await anonymous_client.get("/health")).status_code == 200
        monkeypatch.setattr(core.health, "get_redis_conn", lambda: _BrokenRedis())

        response = await anonymous_client.get("/health")

        assert response.status_code == 200

    async def test_edge_case_pings_again_once_the_ttl_has_passed(
        self, anonymous_client, monkeypatch
    ):
        """Scope: the cache only shortens the check; Redis going down is
        still reported within REDIS_HEALTH_TTL_SECONDS."""
        assert (await anonymous_client.get("/health")).status_code == 200
        later = core.health.monotonic() + core.health.REDIS_HEALTH_TTL_SECONDS + 1
        monkeypatch.setattr(core.health, "monotonic", lambda: later)
        monkeypatch.setattr(core.health, "get_redis_conn", lambda: _BrokenRedis())

        response = await anonymous_client.get("/health")

        assert response.status_code == 503
        assert "redis" in response.json()["detail"]

    async def test_edge_case_a_failure_is_never_reused(self, anonymous_client, monkeypatch):
        """Scope: after a failed ping the next check pings again, so recovery
        shows up immediately."""
        with monkeypatch.context() as patched:
            patched.setattr(core.health, "get_redis_conn", lambda: _BrokenRedis())
            assert (await anonymous_client.get("/health")).status_code == 503

        response = await anonymous_client.get("/health")

        assert response.status_code == 200

    async def test_edge_case_a_cached_ping_never_hides_a_postgres_outage(
        self, anonymous_client, monkeypatch
    ):
        """Scope: Postgres is checked on every call, cached Redis or not."""
        assert (await anonymous_client.get("/health")).status_code == 200

        def _broken_connect(self, *args, **kwargs):
            raise ConnectionError("database is down")

        monkeypatch.setattr(type(core.health.engine), "connect", _broken_connect)

        response = await anonymous_client.get("/health")

        assert response.status_code == 503
        assert "database" in response.json()["detail"]

    async def test_happy_path_connections_skip_client_setinfo(self):
        """Scope: each fresh connection sends AUTH + the command only, not
        two CLIENT SETINFO calls (lib-name/lib-ver) on top."""
        async with core.health.get_redis_conn() as conn:
            info = await conn.client_info()

        assert info.get("lib-name", "") == ""
        assert info.get("lib-ver", "") == ""


class TestVersion:
    async def test_happy_path_reports_the_deployed_commit(self, anonymous_client, monkeypatch):
        monkeypatch.setattr("api.main.settings.render_git_commit", "abc123")

        response = await anonymous_client.get("/version")

        assert response.status_code == 200
        assert response.json() == {"commit": "abc123"}
