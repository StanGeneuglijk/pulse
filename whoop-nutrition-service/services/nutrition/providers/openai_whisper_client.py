"""The only module that calls OpenAI — speech-to-text only."""

from typing import Any, cast

from openai import APIError, AsyncOpenAI

from services.nutrition.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, nutrition_settings
from services.nutrition.exceptions import TranscriptionFailedError
from services.nutrition.transcription import TranscriptionResult

# OpenAI infers the audio format from the filename extension.
_EXTENSION_BY_CONTENT_TYPE = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/m4a": "m4a",
}


class OpenAIWhisperClient:
    def __init__(self, *, api_key: str) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
        )

    async def transcribe(self, *, audio_bytes: bytes, content_type: str) -> TranscriptionResult:
        """Transcribe audio to text.

        Raises:
            TranscriptionFailedError: If the call fails or no speech is detected.
        """
        # Browsers send parameters ("audio/mp4;codecs=mp4a.40.2") — match on the base type.
        base_type = content_type.split(";")[0].strip().lower()
        extension = _EXTENSION_BY_CONTENT_TYPE.get(base_type, "webm")
        try:
            # verbose_json is the only format that returns `duration` (the billing
            # unit); same price. cast: the SDK types each format's response separately.
            response = await self._client.audio.transcriptions.create(
                model=nutrition_settings.transcription_model,
                file=(f"audio.{extension}", audio_bytes, content_type),
                response_format=cast(Any, "verbose_json"),
            )
        except APIError as exc:
            raise TranscriptionFailedError(str(exc)) from exc

        text = response.text.strip()
        if not text:
            raise TranscriptionFailedError("no speech detected in the audio")
        return TranscriptionResult(text=text, duration_seconds=response.duration)
