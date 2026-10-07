"""Provider prices: a dated, versioned table.

A call's cost is computed once, when the call is recorded, with the table current at that
moment, and stored with the table version. It is never recomputed: a price change applies
to new calls only. Costs are estimates from list prices, not the provider's invoice.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from core.schemas import Usage

PER_MILLION = 1_000_000
_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")  # gpt-5.4-mini-2026-03-17 -> gpt-5.4-mini


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1M tokens. Reasoning tokens are output tokens and are billed as output."""

    input: float
    cached_input: float
    output: float


@dataclass(frozen=True)
class PriceTable:
    version: str
    models: Mapping[str, ModelPrice]
    search_credit_usd: float

    def model_price(self, model: str) -> ModelPrice | None:
        return self.models.get(model) or self.models.get(_SNAPSHOT.sub("", model))

    def llm_cost(self, model: str, usage: Usage) -> float | None:
        """None when the model is not in the table or the API did not report the tokens."""
        price = self.model_price(model)
        if price is None or None in (usage.input_tokens, usage.cached_input_tokens, usage.output_tokens):
            return None
        cached = usage.cached_input_tokens
        uncached = usage.input_tokens - cached  # cached tokens are part of input, priced once
        return (uncached * price.input + cached * price.cached_input + usage.output_tokens * price.output) / PER_MILLION

    def search_cost(self, credits: float | None) -> float | None:
        return None if credits is None else credits * self.search_credit_usd


# OpenAI standard tier, short context: https://developers.openai.com/api/docs/pricing
# Tavily pay-as-you-go: https://docs.tavily.com/documentation/api-credits (basic search = 1 credit).
# On the free plan searches cost nothing until the monthly credits run out; they are still priced
# at the pay-as-you-go rate so the estimate shows what a run really costs.
PRICES = PriceTable(
    version="2026-10-07",
    models={
        "gpt-5.4-mini": ModelPrice(input=0.75, cached_input=0.075, output=4.50),
        "gpt-5.4-nano": ModelPrice(input=0.20, cached_input=0.02, output=1.25),
    },
    search_credit_usd=0.008,
)
