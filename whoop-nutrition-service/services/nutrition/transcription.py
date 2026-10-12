"""The speech-to-text seam — separate from the chat seam: different problem,
vendor, secret and billing unit.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranscriptionResult:
    text: str
    duration_seconds: float


class TranscriptionClient(Protocol):
    """Turns recorded audio into text plus its duration (the billing unit)."""

    async def transcribe(
        self, *, audio_bytes: bytes, content_type: str
    ) -> TranscriptionResult: ...
