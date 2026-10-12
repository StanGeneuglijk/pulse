from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import APIError

from services.nutrition.exceptions import TranscriptionFailedError
from services.nutrition.providers.openai_whisper_client import OpenAIWhisperClient


async def test_transcribe_returns_the_text_and_duration():
    client = OpenAIWhisperClient(api_key="test-key")
    client._client.audio.transcriptions.create = AsyncMock(
        return_value=SimpleNamespace(text="I had two eggs and toast", duration=4.2)
    )

    result = await client.transcribe(audio_bytes=b"fake-audio", content_type="audio/webm")

    assert result.text == "I had two eggs and toast"
    assert result.duration_seconds == 4.2


async def test_transcribe_raises_on_empty_result():
    client = OpenAIWhisperClient(api_key="test-key")
    client._client.audio.transcriptions.create = AsyncMock(
        return_value=SimpleNamespace(text="   ", duration=1.0)
    )

    with pytest.raises(TranscriptionFailedError):
        await client.transcribe(audio_bytes=b"fake-audio", content_type="audio/webm")


async def test_transcribe_wraps_an_api_error():
    client = OpenAIWhisperClient(api_key="test-key")
    client._client.audio.transcriptions.create = AsyncMock(
        side_effect=APIError("boom", request=SimpleNamespace(), body=None)
    )

    with pytest.raises(TranscriptionFailedError):
        await client.transcribe(audio_bytes=b"fake-audio", content_type="audio/webm")


async def test_transcribe_ignores_mime_parameters_when_naming_the_file():
    """Safari's MediaRecorder reports e.g. "audio/mp4;codecs=mp4a.40.2" —
    the filename extension (what OpenAI infers the format from) must still be mp4."""
    client = OpenAIWhisperClient(api_key="test-key")
    create = AsyncMock(return_value=SimpleNamespace(text="two eggs", duration=1.0))
    client._client.audio.transcriptions.create = create

    await client.transcribe(audio_bytes=b"fake-audio", content_type="audio/mp4;codecs=mp4a.40.2")

    filename, _, _ = create.call_args.kwargs["file"]
    assert filename == "audio.mp4"
