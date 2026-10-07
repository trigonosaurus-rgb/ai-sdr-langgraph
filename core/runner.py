"""Runs the graph for one brief: numbers events, measures time, decides the honest outcome."""

import logging
from collections.abc import Callable
from itertools import count
from uuid import uuid4

from core.context import BudgetExhausted, RunCancelled, RunContext
from core.events import Completed, Failed, Payload, RunUsage, StageStarted, Started, to_wire
from core.graph import build_graph
from core.schemas import Brief, FailureReason, LLMCall, RunResult, SearchCall, Stage
from core.state import SDRState

log = logging.getLogger(__name__)
EventHandler = Callable[[dict], None]
BUDGET_MESSAGE = "The service was temporarily stopped by the developer during the run. Nothing was finished."


def _sum[N: (int, float)](values: list[N | None]) -> N | None:
    """Total, or None if any value is unknown: a partial sum would understate usage."""
    return None if any(v is None for v in values) else sum(values)  # type: ignore[arg-type,return-value]


def summarize_usage(calls: list[LLMCall], searches: list[SearchCall], duration_ms: int) -> RunUsage:
    usages = [call.usage for call in calls]
    return RunUsage(
        input=_sum([u.input_tokens for u in usages]),
        cached_input=_sum([u.cached_input_tokens for u in usages]),
        output=_sum([u.output_tokens for u in usages]),
        reasoning=_sum([u.reasoning_tokens for u in usages]),
        model_usd=_sum([call.cost_usd for call in calls]),
        search_usd=_sum([call.cost_usd for call in searches]),
        duration_seconds=duration_ms / 1000,
        model=", ".join(dict.fromkeys(call.model for call in calls)),
    )


def _stop_message(reason: FailureReason, state: SDRState) -> str:
    brief, research = state["brief"], state.get("research")
    if reason == "website_mismatch":
        note = research.website_note if research else ""
        return f"Search results do not match {brief.domain}. {note}".strip()
    gaps = f" Missing: {research.gaps}" if research and research.gaps else ""
    return f"Not enough reliable information about {brief.company} to write a specific email.{gaps}"


def run_sdr(
    brief: Brief,
    ctx: RunContext,
    *,
    run_id: str | None = None,
    on_event: EventHandler | None = None,
) -> RunResult:
    run_id = run_id or uuid4().hex
    started_at = ctx.clock()
    sequence = count()
    stage: Stage | None = None

    def elapsed_ms() -> int:
        return round((ctx.clock() - started_at) * 1000)

    def publish(payload: Payload) -> None:
        nonlocal stage
        if isinstance(payload, StageStarted):
            stage = payload.stage
        if isinstance(payload, (StageStarted, Completed, Failed)) and payload.elapsed_ms is None:
            payload = payload.model_copy(update={"elapsed_ms": elapsed_ms()})
        if on_event:
            on_event(to_wire(payload, run_id, next(sequence)))

    publish(Started(company=brief.company, recipient=brief.recipient))
    graph = build_graph(ctx)
    state: SDRState = {"brief": brief}
    error: Exception | None = None
    stopped: FailureReason | None = None
    try:
        for mode, chunk in graph.stream(
            {"brief": brief},
            stream_mode=["custom", "values"],
            config={"recursion_limit": 10 + 2 * (1 + ctx.settings.max_rewrites)},
        ):
            if mode == "custom":
                publish(chunk)
            else:
                state = chunk
    except RunCancelled:
        log.info("run %s cancelled in %s", run_id, stage)
        stopped = "cancelled"
    except BudgetExhausted:
        log.warning("run %s stopped in %s: monthly budget", run_id, stage)
        stopped = "budget_exhausted"
    except Exception as exc:  # any failure ends the run as failed, never as a result
        log.exception("run %s failed in %s", run_id, stage)
        error = exc

    attempts = state.get("attempts", [])
    last = attempts[-1] if attempts else None
    strategy = state.get("strategy")
    reason: FailureReason | None = None
    issues: list[str] = []

    if stopped == "cancelled":
        status, reason = "failed", "cancelled"
        message = public_message = "The run was cancelled. Nothing was finished."
    elif stopped == "budget_exhausted":
        status, reason = "failed", "budget_exhausted"
        message = public_message = BUDGET_MESSAGE
    elif error is not None:
        status, reason = "failed", "error"
        message = f"{stage or 'Run'} step failed: {type(error).__name__}: {error}"
        public_message = f"The {stage or 'run'} step failed. Nothing was finished."
    elif stop := state.get("stop"):
        status, reason = "failed", stop
        message = public_message = _stop_message(stop, state)
    elif last is None or last.review is None:
        status, reason = "failed", "error"
        message = public_message = "The run ended without a reviewed draft."
    elif not last.review.passed:
        status = "needs_attention"
        issues = last.review.issues
        message = f"The draft did not pass review after {last.attempt} attempts."
    elif strategy and strategy.offer_fit == "poor":
        status = "needs_attention"
        issues = [f"The offer may not fit this company: {strategy.fit_reason}"]
        message = "The draft passed review, but the offer looks like a poor fit."
    else:
        status = "ready"
        message = "The draft passed review."

    duration = elapsed_ms()
    if status == "failed":
        publish(Failed(reason=reason, message=public_message, stage=stage, elapsed_ms=duration))
    else:
        publish(
            Completed(
                outcome=status,
                issues=issues,
                usage=summarize_usage(ctx.llm_calls, ctx.search_calls, duration),
                elapsed_ms=duration,
            )
        )

    return RunResult(
        run_id=run_id,
        brief=brief,
        status=status,
        reason=reason,
        message=message,
        issues=issues,
        research=state.get("research"),
        strategy=strategy,
        draft=last.draft if last and status != "failed" else None,
        attempts=attempts,
        prompt_versions=state.get("prompt_versions", {}),
        llm_calls=ctx.llm_calls,
        search_calls=ctx.search_calls,
        duration_ms=duration,
    )
