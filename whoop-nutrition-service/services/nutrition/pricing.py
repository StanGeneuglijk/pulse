"""List prices for both vendors — Claude per token, Whisper per audio minute —
used to estimate spend for the caps and to restrict configurable models.
"""

# USD per million tokens. (input, output).
PRICE_PER_MTOK_USD: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# USD per minute of audio. OpenAI's transcription API bills by input
# audio duration, not tokens.
WHISPER_PRICE_PER_MINUTE_USD: dict[str, float] = {
    "whisper-1": 0.006,
}


def estimate_cost_usd(
    model_name: str, input_tokens: int | None, output_tokens: int | None
) -> float:
    """Estimated cost of one chat call; an unknown model is priced at the most
    expensive rate.
    """
    input_price, output_price = PRICE_PER_MTOK_USD.get(
        model_name, max(PRICE_PER_MTOK_USD.values(), key=lambda p: p[1])
    )
    return (input_tokens or 0) / 1_000_000 * input_price + (
        output_tokens or 0
    ) / 1_000_000 * output_price


def estimate_transcription_cost_usd(model_name: str, duration_seconds: float) -> float:
    """Estimated cost of one transcription; an unknown model is priced at the
    most expensive rate.
    """
    price_per_minute = WHISPER_PRICE_PER_MINUTE_USD.get(
        model_name, max(WHISPER_PRICE_PER_MINUTE_USD.values())
    )
    return duration_seconds / 60 * price_per_minute
