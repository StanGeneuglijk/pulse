"""Anthropic list prices, used to estimate spend for the caps (the invoice is
the source of truth) and to restrict which models can be configured.
"""

# USD per million tokens. (input, output).
PRICE_PER_MTOK_USD: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_cost_usd(
    model_name: str, input_tokens: int | None, output_tokens: int | None
) -> float:
    """Estimated cost of one call; an unknown model is priced at the most
    expensive rate, erring toward stopping early.
    """
    input_price, output_price = PRICE_PER_MTOK_USD.get(
        model_name, max(PRICE_PER_MTOK_USD.values(), key=lambda p: p[1])
    )
    return (input_tokens or 0) / 1_000_000 * input_price + (
        output_tokens or 0
    ) / 1_000_000 * output_price
