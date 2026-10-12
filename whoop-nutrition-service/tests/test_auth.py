import uuid

from httpx import ASGITransport, AsyncClient

from api.main import app
from tests.conftest import AUTH_HEADERS, seed_read_token


def _client_as(token: str) -> AsyncClient:
    """An HTTP client authenticated with a specific bearer token — for
    read_token scoping tests, where the token under test isn't the
    operator API_KEY `client`/`AUTH_HEADERS` carry."""
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}
    )


async def test_missing_auth_header_is_rejected(anonymous_client, db_session):
    response = await anonymous_client.get(f"/nutrition/{uuid.uuid4()}/usage")
    assert response.status_code == 401


async def test_master_api_key_grants_access_to_any_user(client, db_session):
    # No users_table fixture here on purpose — the master key path never
    # queries whoop-service's users table at all (see auth.py), so this
    # must succeed even without it existing.
    response = await client.get(f"/nutrition/{uuid.uuid4()}/usage")
    assert response.status_code == 200


async def test_users_own_read_token_grants_access_to_their_own_data(db_session, users_table):
    user_id = uuid.uuid4()
    await seed_read_token(db_session, user_id, "the-real-token")

    async with _client_as("the-real-token") as ac:
        response = await ac.get(f"/nutrition/{user_id}/usage")

    assert response.status_code == 200


async def test_users_read_token_does_not_grant_access_to_another_users_data(
    db_session, users_table
):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    await seed_read_token(db_session, owner_id, "owners-token")
    await seed_read_token(db_session, other_id, "others-token")

    async with _client_as("owners-token") as ac:
        response = await ac.get(f"/nutrition/{other_id}/usage")

    assert response.status_code == 401


async def test_spend_is_operator_only_a_users_own_read_token_is_rejected(db_session, users_table):
    user_id = uuid.uuid4()
    await seed_read_token(db_session, user_id, "the-real-token")

    async with _client_as("the-real-token") as ac:
        response = await ac.get("/nutrition/spend")

    assert response.status_code == 401


class TestConversationOwnerAuth:
    """The confirm/discard routes are keyed by conversation_id, not
    user_id — require_conversation_owner resolves the conversation's own
    user_id first, then checks the same way require_user_access does."""

    async def _create_conversation(self, user_id: uuid.UUID) -> uuid.UUID:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=AUTH_HEADERS
        ) as ac:
            response = await ac.post(f"/nutrition/chat/{user_id}", json={"message": "hi"})
        return uuid.UUID(response.json()["conversationId"])

    async def test_owners_read_token_can_discard_their_own_conversation(
        self, db_session, fake_llm_client, users_table
    ):
        owner_id = uuid.uuid4()
        await seed_read_token(db_session, owner_id, "owners-token")
        conversation_id = await self._create_conversation(owner_id)

        async with _client_as("owners-token") as ac:
            response = await ac.post(f"/nutrition/meals/discard/{conversation_id}")

        # No pending meal was staged (plain text reply), so this is a
        # domain 409, not a 401 — proves auth passed and the request
        # reached the route handler.
        assert response.status_code == 409

    async def test_another_users_read_token_cannot_touch_this_conversation(
        self, db_session, fake_llm_client, users_table
    ):
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        await seed_read_token(db_session, owner_id, "owners-token")
        await seed_read_token(db_session, other_id, "others-token")
        conversation_id = await self._create_conversation(owner_id)

        async with _client_as("others-token") as ac:
            response = await ac.post(f"/nutrition/meals/discard/{conversation_id}")

        assert response.status_code == 401

    async def test_master_key_reaches_the_routes_own_not_found_for_a_bad_conversation_id(
        self, db_session
    ):
        # No users_table fixture — the master-key fast path in
        # require_conversation_owner must never touch it, and must never
        # need the conversation to exist either; that's the route
        # handler's own job.
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=AUTH_HEADERS
        ) as ac:
            response = await ac.post(f"/nutrition/meals/discard/{uuid.uuid4()}")

        assert response.status_code == 404

    async def test_unknown_token_gets_401_not_the_routes_not_found(self, db_session, users_table):
        async with _client_as("not-a-real-token") as ac:
            response = await ac.post(f"/nutrition/meals/discard/{uuid.uuid4()}")

        assert response.status_code == 401
