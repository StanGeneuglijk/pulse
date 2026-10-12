import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import respx
from httpx import Response
from sqlalchemy import select

from core.config import settings
from core.crypto import decrypt_token
from services.whoop import crud, router
from services.whoop.config import WHOOP_AUTH_URL, whoop_settings
from services.whoop.models import User


class TestAuth:
    """OAuth login/callback — both routes are deliberately unauthenticated
    (they establish or exchange a WHOOP credential, not this service's
    own caller auth), so every test here uses anonymous_client."""

    async def test_happy_path_login_redirects_to_whoop_with_a_tracked_state(
        self, anonymous_client
    ):
        """Scope: /auth/login must redirect to WHOOP's own login page
        with this app's real client_id/redirect_uri/scope, carrying a
        `state` the callback route can later verify — the CSRF
        protection the whole OAuth flow depends on."""
        response = await anonymous_client.get("/auth/login", follow_redirects=False)

        assert response.status_code in (302, 307)
        location = urlparse(response.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == WHOOP_AUTH_URL

        params = parse_qs(location.query)
        assert params["client_id"] == [whoop_settings.whoop_client_id]
        assert params["redirect_uri"] == [whoop_settings.whoop_redirect_uri]
        assert params["response_type"] == ["code"]
        state = params["state"][0]
        code_verifier = await router._oauth_states.consume(state)
        assert code_verifier is not None  # recorded, and consumable exactly once

    async def test_happy_path_login_includes_a_pkce_challenge_matching_the_verifier(
        self, anonymous_client
    ):
        """Scope: PKCE (RFC 7636) — the redirect must carry a S256
        code_challenge derived from the verifier stashed alongside
        `state`, so callback() can later prove possession of the same
        verifier at token-exchange time."""
        response = await anonymous_client.get("/auth/login", follow_redirects=False)

        params = parse_qs(urlparse(response.headers["location"]).query)
        assert params["code_challenge_method"] == ["S256"]
        state = params["state"][0]
        code_verifier = await router._oauth_states.consume(state)

        expected_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        assert params["code_challenge"] == [expected_challenge]

    async def test_edge_case_callback_rejects_an_unknown_state(self, anonymous_client):
        """Scope: the fail-fast/loud/clear chain end to end —
        router.py raises InvalidOAuthStateError immediately,
        api/main.py's registered handler maps it to a clear 400 — no
        code exchange is ever attempted."""
        response = await anonymous_client.get(
            "/auth/callback", params={"code": "irrelevant", "state": "bogus"}
        )

        assert response.status_code == 400
        assert "invalid or missing" in response.json()["detail"]

    @respx.mock
    async def test_happy_path_callback_redirects_to_the_frontend_with_an_exchange_code(
        self, anonymous_client, db_session
    ):
        """Scope: the browser must land back on the frontend, carrying a
        one-time code rather than the real read_token — the token itself
        never appears in this redirect's URL. See core/one_time_code.py."""
        await router._oauth_states.create("known-state", "known-code-verifier")
        _mock_profile(whoop_user_id=4242)
        token_route = respx.post("https://api.prod.whoop.com/oauth/oauth2/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 3600,
                },
            )
        )

        response = await anonymous_client.get(
            "/auth/callback",
            params={"code": "irrelevant", "state": "known-state"},
            follow_redirects=False,
        )

        assert response.status_code in (302, 307)
        location = urlparse(response.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == (
            f"{settings.frontend_url}/connected"
        )
        code = parse_qs(location.query)["code"][0]
        assert "read_token" not in response.headers["location"]  # never in the URL itself
        payload = await router._exchange_codes.consume(code)
        assert payload  # recorded, not just a truthy check — inspected below

        # PKCE: the verifier stashed alongside `state` in login() must
        # actually be sent back at token-exchange time, not just stored.
        sent_body = parse_qs(token_route.calls.last.request.content.decode())
        assert sent_body["code_verifier"] == ["known-code-verifier"]

        # The actual acceptance criterion: a real User row landed in the
        # database, with encrypted (not plaintext) tokens and a populated
        # read_token — not just a plausible-looking redirect.
        user = await crud.get_user(db_session, payload["user_id"])
        assert user.encrypted_access_token not in (None, "new-access-token")
        assert user.encrypted_refresh_token not in (None, "new-refresh-token")
        assert decrypt_token(user.encrypted_access_token, settings.token_encryption_key) == (
            "new-access-token"
        )
        assert user.read_token is not None
        assert user.read_token == payload["read_token"]


class TestExchange:
    """POST /auth/exchange — the frontend's one shot at redeeming a
    callback() redirect for the real read_token. Deliberately
    unauthenticated, like login/callback: the code itself is the
    credential."""

    async def test_happy_path_redeems_a_valid_code(self, anonymous_client):
        code = await router._exchange_codes.create(
            {"user_id": "11111111-1111-1111-1111-111111111111", "read_token": "the-real-token"}
        )

        response = await anonymous_client.post("/auth/exchange", json={"code": code})

        assert response.status_code == 200
        body = response.json()
        assert body["connected"] is True
        assert body["readToken"] == "the-real-token"
        assert body["userId"] == "11111111-1111-1111-1111-111111111111"

    async def test_edge_case_rejects_an_unknown_code(self, anonymous_client):
        response = await anonymous_client.post("/auth/exchange", json={"code": "never-issued"})

        assert response.status_code == 401

    async def test_edge_case_a_code_can_only_be_exchanged_once(self, anonymous_client):
        """Scope: replay protection — a code intercepted after its first,
        legitimate use must be worthless to a second caller."""
        code = await router._exchange_codes.create(
            {"user_id": "11111111-1111-1111-1111-111111111111", "read_token": "the-real-token"}
        )
        first = await anonymous_client.post("/auth/exchange", json={"code": code})

        second = await anonymous_client.post("/auth/exchange", json={"code": code})

        assert first.status_code == 200
        assert second.status_code == 401


def _mock_profile(whoop_user_id: int) -> None:
    respx.get(url__regex=r".*/v2/user/profile/basic").mock(
        return_value=Response(200, json={"user_id": whoop_user_id})
    )


def _mock_token_exchange(access_token: str) -> None:
    respx.post("https://api.prod.whoop.com/oauth/oauth2/token").mock(
        return_value=Response(
            200,
            json={"access_token": access_token, "refresh_token": "r", "expires_in": 3600},
        )
    )


async def _connect(anonymous_client, state: str) -> dict:
    await router._oauth_states.create(state, "verifier")
    response = await anonymous_client.get(
        "/auth/callback", params={"code": "c", "state": state}, follow_redirects=False
    )
    code = parse_qs(urlparse(response.headers["location"]).query)["code"][0]
    payload = await router._exchange_codes.consume(code)
    assert payload is not None
    return payload


class TestReconnect:
    """Connecting the same WHOOP account twice must reuse one user."""

    @respx.mock
    async def test_happy_path_reconnecting_the_same_account_reuses_the_user(
        self, anonymous_client, db_session
    ):
        _mock_profile(whoop_user_id=777)
        _mock_token_exchange("first-access-token")
        first = await _connect(anonymous_client, "state-1")

        _mock_token_exchange("second-access-token")
        second = await _connect(anonymous_client, "state-2")

        assert second["user_id"] == first["user_id"]
        assert second["read_token"] == first["read_token"]  # existing sessions stay valid
        rows = await db_session.execute(select(User).where(User.whoop_user_id == "777"))
        user = rows.scalars().one()
        assert decrypt_token(user.encrypted_access_token, settings.token_encryption_key) == (
            "second-access-token"
        )

    @respx.mock
    async def test_edge_case_a_different_account_gets_its_own_user(
        self, anonymous_client, db_session
    ):
        _mock_token_exchange("a")
        _mock_profile(whoop_user_id=1)
        first = await _connect(anonymous_client, "state-a")
        _mock_profile(whoop_user_id=2)
        second = await _connect(anonymous_client, "state-b")

        assert second["user_id"] != first["user_id"]
