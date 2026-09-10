"""Configurable token pricing; unknown models remain explicitly unpriced."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_million: float
    output_per_million: float


def estimate_cost(
    input_tokens: int | None, output_tokens: int | None, price: Price
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    return (
        input_tokens * price.input_per_million + output_tokens * price.output_per_million
    ) / 1_000_000


def price_for(model: str, prices: dict[str, Price]) -> Price | None:
    if model in prices:
        return prices[model]
    candidates = [(prefix, price) for prefix, price in prices.items() if model.startswith(prefix)]
    return max(candidates, key=lambda item: len(item[0]))[1] if candidates else None
