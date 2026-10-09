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
    cache_write: float | None = None  # None: writing to the prompt cache costs nothing extra


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
        if price.cache_write is None:
            written, write_price = 0, 0.0  # any written tokens are ordinary input
        elif usage.cache_write_tokens is None:
            return None  # the write surcharge is unknown
        else:
            written, write_price = usage.cache_write_tokens, price.cache_write
        cached = usage.cached_input_tokens
        ordinary = usage.input_tokens - cached - written  # cached and written are part of input, priced once
        input_cost = ordinary * price.input + cached * price.cached_input + written * write_price
        return (input_cost + usage.output_tokens * price.output) / PER_MILLION

    def search_cost(self, credits: float | None) -> float | None:
        return None if credits is None else credits * self.search_credit_usd


# OpenAI standard tier, short context: https://developers.openai.com/api/docs/pricing
# GPT-5.6 and later bill prompt-cache writes at 1.25x input:
# https://developers.openai.com/api/docs/guides/prompt-caching
# Tavily pay-as-you-go: https://docs.tavily.com/documentation/api-credits (basic search = 1 credit).
# On the free plan searches cost nothing until the monthly credits run out; they are still priced
# at the pay-as-you-go rate so the estimate shows what a run really costs.
PRICES = PriceTable(
    version="2026-10-09",
    models={
        "gpt-5.4-mini": ModelPrice(input=0.75, cached_input=0.075, output=4.50),
        "gpt-5.4-nano": ModelPrice(input=0.20, cached_input=0.02, output=1.25),
        "gpt-6-luna": ModelPrice(input=0.10, cached_input=0.01, output=0.50, cache_write=0.125),
        "gpt-6.1-sol": ModelPrice(input=2.00, cached_input=0.10, output=10.00, cache_write=2.50),
    },
    search_credit_usd=0.008,
)
