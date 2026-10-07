"""Prices and costs: tariff arithmetic, no double counting, unknown usage, the daily-limit stop."""

import pytest

from core.config import Settings
from core.context import DailyLimitReached, RunContext
from core.llm import LLMError
from core.pricing import PRICES, ModelPrice, PriceTable
from core.runner import run_sdr
from core.schemas import Usage
from fakes import FakeClock, FakeLLM, happy_script

MINI = "gpt-5.4-mini"
TABLE = PriceTable(
    version="test-1",
    models={"fake-model": ModelPrice(input=1.0, cached_input=0.1, output=10.0)},
    search_credit_usd=0.01,
)


def test_llm_cost_prices_cached_input_and_output_once():
    usage = Usage(input_tokens=1000, cached_input_tokens=200, output_tokens=500, reasoning_tokens=300)
    # 800 uncached input + 200 cached input + 500 output; reasoning is inside output, not added
    expected = (800 * 0.75 + 200 * 0.075 + 500 * 4.50) / 1_000_000
    assert PRICES.llm_cost(MINI, usage) == pytest.approx(expected)
    no_reasoning = usage.model_copy(update={"reasoning_tokens": 0})
    assert PRICES.llm_cost(MINI, no_reasoning) == pytest.approx(expected)


def test_snapshot_names_use_the_base_model_price():
    usage = Usage(input_tokens=1_000_000, cached_input_tokens=0, output_tokens=0)
    assert PRICES.llm_cost("gpt-5.4-mini-2026-03-17", usage) == pytest.approx(0.75)
    assert PRICES.model_price("gpt-5.4-mini-2026") is None  # only a full date suffix is a snapshot


@pytest.mark.parametrize(
    ("model", "usage"),
    [
        ("gpt-unknown", Usage(input_tokens=10, cached_input_tokens=0, output_tokens=10)),
        (MINI, Usage()),
        (MINI, Usage(input_tokens=10, output_tokens=10)),  # cached share unknown
        (MINI, Usage(input_tokens=10, cached_input_tokens=0)),
    ],
)
def test_unknown_model_or_usage_has_no_cost(model, usage):
    assert PRICES.llm_cost(model, usage) is None


def test_search_cost_follows_reported_credits():
    assert PRICES.search_cost(3) == pytest.approx(0.024)
    assert PRICES.search_cost(0) == 0
    assert PRICES.search_cost(None) is None


def make_ctx(llm, search, **kwargs) -> RunContext:
    return RunContext(settings=Settings(), llm=llm, search_client=search, clock=FakeClock(), prices=TABLE, **kwargs)


def test_each_call_is_priced_and_reported_when_it_ends(brief, search):
    recorded = []
    ctx = make_ctx(FakeLLM(happy_script()), search, on_record=recorded.append)
    result = run_sdr(brief, ctx)

    assert recorded == [*result.search_calls, *result.llm_calls]  # three searches, then four LLM calls
    call = result.llm_calls[0]  # 100 input (20 cached), 50 output
    assert call.cost_usd == pytest.approx((80 * 1.0 + 20 * 0.1 + 50 * 10.0) / 1_000_000)
    assert {c.price_version for c in result.llm_calls + result.search_calls} == {"test-1"}
    assert [c.cost_usd for c in result.search_calls] == [0.01, 0.01, 0.01]


def test_run_usage_totals_costs_and_stays_unknown_if_any_call_is(brief, search):
    events = []
    run_sdr(brief, make_ctx(FakeLLM(happy_script()), search), on_event=events.append)
    totals = events[-1]["usage"]
    assert totals["modelUsd"] == pytest.approx(4 * 582 / 1_000_000)
    assert totals["searchUsd"] == pytest.approx(0.03)
    assert totals["input"] == 400 and totals["cachedInput"] == 80  # cached stays a subset

    events = []
    unpriced = FakeLLM(happy_script(), model="other-model")
    run_sdr(brief, make_ctx(unpriced, search), on_event=events.append)
    assert events[-1]["usage"]["modelUsd"] is None  # never a partial sum or zero


def test_failed_call_keeps_the_usage_the_api_reported(brief, search):
    usage = Usage(input_tokens=100, cached_input_tokens=0, output_tokens=0)
    error = LLMError("cut at length limit", usage=usage, model="fake-model")
    ctx = make_ctx(FakeLLM(happy_script(Research=[error])), search)
    result = run_sdr(brief, ctx)

    assert result.status == "failed"
    assert result.llm_calls[0].error and result.llm_calls[0].cost_usd == pytest.approx(100 / 1_000_000)


def test_daily_limit_stops_before_the_next_paid_call(brief, search):
    llm = FakeLLM(happy_script())
    seen = []

    def before_call(kind):
        seen.append(kind)
        if len(seen) > 4:  # three searches and the Research call pass
            raise DailyLimitReached

    events = []
    result = run_sdr(brief, make_ctx(llm, search, before_call=before_call), on_event=events.append)

    assert seen == ["search", "search", "search", "llm", "llm"]
    assert llm.stages() == ["Research"]
    assert result.status == "failed" and result.reason == "daily_limit"
    assert events[-1]["type"] == "failed" and events[-1]["reason"] == "daily_limit"
    assert events[-1]["stage"] == "Strategy"
