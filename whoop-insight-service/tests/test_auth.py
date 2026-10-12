import uuid

from httpx import ASGITransport, AsyncClient

from api.main import app
from tests.conftest import seed_read_token


def _client_as(token: str) -> AsyncClient:
    """An HTTP client authenticated with a specific bearer token — for
    read_token scoping tests, where the token under test isn't the
    operator API_KEY conftest's `client` fixture carries. Mirrors
    whoop-service's own tests/test_reads.py helper of the same name."""
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}
    )


async def test_missing_auth_header_is_rejected(anonymous_client, db_session):
    response = await anonymous_client.get(f"/insights/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_master_api_key_grants_access_to_any_user(client, db_session):
    # No users_table fixture here on purpose — the master key path never
    # queries whoop-service's users table at all (see auth.py), so this
    # must succeed even without it existing.
    response = await client.get(f"/insights/{uuid.uuid4()}")
    assert response.status_code == 200


async def test_users_own_read_token_grants_access_to_their_own_data(
    db_session, users_table
):
    user_id = uuid.uuid4()
    await seed_read_token(db_session, user_id, "the-real-token")

    async with _client_as("the-real-token") as ac:
        response = await ac.get(f"/insights/{user_id}")

    assert response.status_code == 200


async def test_users_read_token_does_not_grant_access_to_another_users_data(
    db_session, users_table
):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    await seed_read_token(db_session, owner_id, "owners-token")
    await seed_read_token(db_session, other_id, "others-token")

    async with _client_as("owners-token") as ac:
        response = await ac.get(f"/insights/{other_id}")

    assert response.status_code == 401


async def test_unknown_token_is_rejected(db_session, users_table):
    async with _client_as("not-a-real-token") as ac:
        response = await ac.get(f"/insights/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_spend_is_operator_only_a_users_own_read_token_is_rejected(
    db_session, users_table
):
    user_id = uuid.uuid4()
    await seed_read_token(db_session, user_id, "the-real-token")

    async with _client_as("the-real-token") as ac:
        response = await ac.get("/insights/spend")

    assert response.status_code == 401
