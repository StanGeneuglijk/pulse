import uuid

from services.nutrition import router as router_module
from services.nutrition.config import NUTRITION_MAX_MESSAGE_CHARS, NUTRITION_SPEND_LIMIT_USD
from services.nutrition.crud import write_nutrition_job_log
from tests.conftest import AUTH_HEADERS, sample_meal_proposal


async def test_chat_returns_a_reply_and_stages_a_pending_meal(client, db_session, fake_llm_client):
    fake_llm_client.text = "Here's what I calculated:"
    fake_llm_client.tool_call = sample_meal_proposal()
    user_id = uuid.uuid4()

    response = await client.post(f"/nutrition/chat/{user_id}", json={"message": "two eggs"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Here's what I calculated:"
    assert body["pendingMeal"]["totalCalories"] == 450


async def test_confirm_then_discard_flow(client, db_session, fake_llm_client):
    fake_llm_client.tool_call = sample_meal_proposal()
    user_id = uuid.uuid4()
    chat_response = await client.post(f"/nutrition/chat/{user_id}", json={"message": "two eggs"})
    conversation_id = chat_response.json()["conversationId"]

    confirmed = await client.post(f"/nutrition/meals/confirm/{conversation_id}")
    assert confirmed.status_code == 201
    assert confirmed.json()["calories"] == 450

    # nothing left pending — confirming again is a 409, not a duplicate write
    again = await client.post(f"/nutrition/meals/confirm/{conversation_id}")
    assert again.status_code == 409


async def test_discard_clears_pending_without_saving(client, db_session, fake_llm_client):
    fake_llm_client.tool_call = sample_meal_proposal()
    user_id = uuid.uuid4()
    chat_response = await client.post(f"/nutrition/chat/{user_id}", json={"message": "two eggs"})
    conversation_id = chat_response.json()["conversationId"]

    discarded = await client.post(f"/nutrition/meals/discard/{conversation_id}")
    assert discarded.status_code == 204

    meals = await client.get(f"/nutrition/meals/{user_id}")
    assert meals.json() == []


async def test_summary_reflects_a_confirmed_meal(client, db_session, fake_llm_client):
    fake_llm_client.tool_call = sample_meal_proposal()
    user_id = uuid.uuid4()
    chat_response = await client.post(f"/nutrition/chat/{user_id}", json={"message": "two eggs"})
    conversation_id = chat_response.json()["conversationId"]
    await client.post(f"/nutrition/meals/confirm/{conversation_id}")

    summary = await client.get(f"/nutrition/meals/{user_id}/summary?period=daily")

    assert summary.status_code == 200
    assert summary.json()["totalCalories"] == 450


async def test_goal_set_then_get(client, db_session):
    user_id = uuid.uuid4()

    put_response = await client.put(
        f"/nutrition/goals/{user_id}",
        json={"goalType": "weight_loss", "targetCalories": 1800},
    )
    assert put_response.status_code == 200
    assert put_response.json()["isActive"] is True

    get_response = await client.get(f"/nutrition/goals/{user_id}")
    assert get_response.json()["targetCalories"] == 1800


async def test_get_goal_with_none_set_returns_null(client, db_session):
    response = await client.get(f"/nutrition/goals/{uuid.uuid4()}")
    assert response.status_code == 200
    assert response.json() is None


async def test_spend_endpoint_reports_zero_before_any_chat(client, db_session):
    response = await client.get("/nutrition/spend")
    assert response.status_code == 200
    body = response.json()
    assert body["spentUsd"] == 0
    assert body["limitUsd"] == NUTRITION_SPEND_LIMIT_USD


async def test_chat_returns_402_once_spend_cap_is_reached(client, db_session):
    over_cap_tokens = int(NUTRITION_SPEND_LIMIT_USD / (10.00 / 1_000_000)) + 1_000
    await write_nutrition_job_log(
        db_session,
        user_id=uuid.uuid4(),
        status="success",
        model_name="claude-sonnet-5",
        input_tokens=0,
        output_tokens=over_cap_tokens,
        duration_ms=1.0,
    )

    response = await client.post(f"/nutrition/chat/{uuid.uuid4()}", json={"message": "hi"})

    assert response.status_code == 402


async def test_activity_and_usage(client, db_session, fake_llm_client):
    fake_llm_client.tool_call = sample_meal_proposal()
    user_id = uuid.uuid4()
    chat_response = await client.post(f"/nutrition/chat/{user_id}", json={"message": "two eggs"})
    conversation_id = chat_response.json()["conversationId"]
    await client.post(f"/nutrition/meals/confirm/{conversation_id}")

    activity = await client.get(f"/nutrition/{user_id}/activity")
    assert "chat" in [row["route"] for row in activity.json()]

    usage = await client.get(f"/nutrition/{user_id}/usage")
    assert usage.json()["mealsLogged"] == 1


async def test_chat_audio_transcribes_and_runs_the_same_pipeline(
    client, db_session, fake_llm_client, fake_transcription_client
):
    fake_transcription_client.text = "I had two eggs and toast"
    fake_llm_client.text = "Got it, how much toast?"
    user_id = uuid.uuid4()

    response = await client.post(
        f"/nutrition/chat/{user_id}/audio",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "I had two eggs and toast"
    assert body["reply"] == "Got it, how much toast?"
    assert fake_transcription_client.calls == 1


async def test_chat_audio_returns_503_when_not_configured(anonymous_client, db_session):
    # No fake_transcription_client override here on purpose — proves the
    # real "not configured" path (empty OPENAI_API_KEY, per conftest.py)
    # surfaces as 503, not a crash. Uses anonymous_client + the real
    # header instead of `client` specifically to avoid that fixture's
    # transcription override.
    response = await anonymous_client.post(
        f"/nutrition/chat/{uuid.uuid4()}/audio",
        headers=AUTH_HEADERS,
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 503


async def test_chat_audio_logs_a_transcription_job_that_folds_into_spend(
    client, db_session, fake_llm_client, fake_transcription_client
):
    fake_transcription_client.duration_seconds = 60.0
    user_id = uuid.uuid4()

    response = await client.post(
        f"/nutrition/chat/{user_id}/audio",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    spend = await client.get("/nutrition/spend")
    # 0.006 usd/minute (whisper-1) * 1 minute, plus whatever the fake
    # chat call itself billed — just proves transcription cost is no
    # longer a free blind spot, not the exact chat-side number.
    assert spend.json()["spentUsd"] >= 0.006


async def test_chat_audio_returns_402_once_spend_cap_is_reached_without_transcribing(
    client, db_session, fake_transcription_client
):
    over_cap_seconds = (NUTRITION_SPEND_LIMIT_USD / 0.006) * 60 + 60
    await write_nutrition_job_log(
        db_session,
        user_id=uuid.uuid4(),
        status="success",
        model_name="whisper-1",
        audio_seconds=over_cap_seconds,
        duration_ms=1.0,
    )

    response = await client.post(
        f"/nutrition/chat/{uuid.uuid4()}/audio",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 402
    assert fake_transcription_client.calls == 0


async def test_chat_audio_logs_a_failed_job_when_transcription_raises(
    client, db_session, fake_transcription_client
):
    from services.nutrition.exceptions import TranscriptionFailedError

    fake_transcription_client.raises = TranscriptionFailedError("no speech detected")
    user_id = uuid.uuid4()

    response = await client.post(
        f"/nutrition/chat/{user_id}/audio",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )

    assert response.status_code == 422
    # A failed transcription attempt has no audio_seconds (duration is
    # never known), so it correctly contributes nothing to spend — only
    # a successful one prices anything, same as the chat side.
    usage = await client.get(f"/nutrition/{user_id}/usage")
    assert usage.json()["spendUsd"] == 0.0


async def test_unauthenticated_request_is_rejected(anonymous_client, db_session):
    response = await anonymous_client.get(f"/nutrition/{uuid.uuid4()}/activity")
    assert response.status_code == 401


async def test_chat_rejects_an_over_long_message(client, db_session):
    response = await client.post(
        f"/nutrition/chat/{uuid.uuid4()}",
        json={"message": "x" * (NUTRITION_MAX_MESSAGE_CHARS + 1)},
    )

    assert response.status_code == 422


async def test_chat_audio_rejects_an_oversized_upload(
    client, db_session, fake_llm_client, fake_transcription_client, monkeypatch
):
    monkeypatch.setattr(router_module, "NUTRITION_MAX_AUDIO_BYTES", 10)

    response = await client.post(
        f"/nutrition/chat/{uuid.uuid4()}/audio",
        files={"audio": ("clip.webm", b"x" * 11, "audio/webm")},
    )

    assert response.status_code == 413
