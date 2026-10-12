import core.health


async def test_ok_when_both_dependencies_are_reachable(anonymous_client):
    response = await anonymous_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_503_when_postgres_is_unreachable(anonymous_client, monkeypatch):
    def _broken_connect(self, *args, **kwargs):
        raise ConnectionError("database is down")

    # AsyncEngine.connect is a read-only instance attribute — patch the
    # class instead, scoped back automatically when the test ends.
    monkeypatch.setattr(type(core.health.engine), "connect", _broken_connect)

    response = await anonymous_client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert "database" in body["detail"]


async def test_503_when_redis_is_unreachable(anonymous_client, monkeypatch):
    class _BrokenConn:
        async def ping(self) -> bool:
            raise ConnectionError("redis is down")

        async def __aenter__(self) -> "_BrokenConn":
            return self

        async def __aexit__(self, *exc_info) -> None:
            return None

    # get_redis_conn() builds a fresh connection per call — patch the
    # factory itself, since there's no persistent instance to patch.
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


# Render polls /health every ~10 s per service; a Redis ping each time used
# ~100K Upstash commands a day against a 500K/month free plan.


async def test_a_recent_successful_redis_ping_is_reused(anonymous_client, monkeypatch):
    assert (await anonymous_client.get("/health")).status_code == 200
    monkeypatch.setattr(core.health, "get_redis_conn", lambda: _BrokenRedis())

    response = await anonymous_client.get("/health")

    assert response.status_code == 200


async def test_redis_is_pinged_again_once_the_ttl_has_passed(anonymous_client, monkeypatch):
    assert (await anonymous_client.get("/health")).status_code == 200
    later = core.health.monotonic() + core.health.REDIS_HEALTH_TTL_SECONDS + 1
    monkeypatch.setattr(core.health, "monotonic", lambda: later)
    monkeypatch.setattr(core.health, "get_redis_conn", lambda: _BrokenRedis())

    response = await anonymous_client.get("/health")

    assert response.status_code == 503
    assert "redis" in response.json()["detail"]


async def test_a_failed_redis_ping_is_never_reused(anonymous_client, monkeypatch):
    with monkeypatch.context() as patched:
        patched.setattr(core.health, "get_redis_conn", lambda: _BrokenRedis())
        assert (await anonymous_client.get("/health")).status_code == 503

    response = await anonymous_client.get("/health")

    assert response.status_code == 200


async def test_a_cached_redis_ping_never_hides_a_postgres_outage(anonymous_client, monkeypatch):
    assert (await anonymous_client.get("/health")).status_code == 200

    def _broken_connect(self, *args, **kwargs):
        raise ConnectionError("database is down")

    monkeypatch.setattr(type(core.health.engine), "connect", _broken_connect)

    response = await anonymous_client.get("/health")

    assert response.status_code == 503
    assert "database" in response.json()["detail"]


async def test_redis_connections_skip_client_setinfo():
    async with core.health.get_redis_conn() as conn:
        info = await conn.client_info()

    assert info.get("lib-name", "") == ""
    assert info.get("lib-ver", "") == ""


async def test_version_reports_the_deployed_commit(anonymous_client, monkeypatch):
    monkeypatch.setattr("api.main.settings.render_git_commit", "abc123")

    response = await anonymous_client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"commit": "abc123"}
