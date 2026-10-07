"""Runs graphs in worker threads, persists their events and wakes the SSE streams that follow them."""

import asyncio
import logging
import math
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from core.context import BudgetExhausted, CallKind, RunContext
from core.events import Failed, Started, to_wire
from core.runner import run_sdr
from core.schemas import Brief, LLMCall, SearchCall
from server.store import TERMINAL_EVENTS, CamelModel, Store

log = logging.getLogger(__name__)
ContextFactory = Callable[[Brief, threading.Event], RunContext]
Listener = tuple[asyncio.AbstractEventLoop, asyncio.Event]

PUBLIC_CRASH_MESSAGE = "The run stopped unexpectedly. Nothing was finished."


@dataclass(frozen=True)
class MonthlyBudget:
    """Service-wide spending per calendar month in UTC, all visitors together; Tavily's free credits
    reset on the 1st too. Model spending is real money; web search is counted in provider credits.
    A new run starts only if it fits with a reserve for itself and for every run in progress;
    each paid call is checked again."""

    model_usd: float = 5.0
    search_credits: float = 750
    run_model_usd: float = 0.05  # reserve per run: a run with every rewrite stays below it
    run_search_credits: float = 3  # searches per run, one credit each


@dataclass(frozen=True)
class VisitorQuota:
    """Runs per client address over rolling windows, so one visitor cannot use up the month."""

    per_day: int = 3  # 24 hours
    per_month: int = 10  # 30 days


class BudgetStatus(CamelModel):
    model_usd: float
    spent_model_usd: float
    search_credits: float
    spent_search_credits: float
    paused: bool  # a new run does not fit until the month resets
    resets_at: str  # the 1st of next month, 00:00 UTC


class VisitorStatus(CamelModel):
    runs_per_day: int
    runs_today: int  # last 24 hours
    runs_per_month: int
    runs_this_month: int  # last 30 days
    running: bool
    next_run_at: str | None  # when the quota frees up again, if it is used up


def month_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(moment: datetime) -> datetime:
    start = month_start(moment)
    return start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)


def wait_text(seconds: float) -> str:
    minutes = math.ceil(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours = math.ceil(seconds / 3600)
    return f"{hours} h" if hours < 48 else f"{math.ceil(seconds / 86400)} days"


def month_day(moment: datetime) -> str:
    return f"{moment:%B} {moment.day}"


class RunLimitError(Exception):
    """The client may not start a run now; retry_after is in seconds when a wait will help."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class RunManager:
    def __init__(
        self,
        store: Store,
        make_context: ContextFactory,
        *,
        max_workers: int = 4,
        quota: VisitorQuota = VisitorQuota(),
        budget: MonthlyBudget = MonthlyBudget(),
    ):
        self.store = store
        self.quota = quota
        self.budget = budget
        self._make_context = make_context
        self._start_lock = threading.Lock()  # the limit check and the insert are one step
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sdr-run")
        self._lock = threading.Lock()
        self._cancels: dict[str, threading.Event] = {}
        self._listeners: dict[str, set[Listener]] = {}

    # --- lifecycle

    def fail_interrupted(self, message: str) -> list[str]:
        """Close runs left 'running' by a previous process: nothing can resume them."""
        run_ids = [run_id for run_id in self.store.running_run_ids() if run_id not in self._cancels]
        for run_id in run_ids:
            self._fail(run_id, message)
        return run_ids

    def shutdown(self) -> None:
        """Cancel active runs and wait for them to stop; each stops before its next paid call."""
        with self._lock:
            for cancel in self._cancels.values():
                cancel.set()
        self._executor.shutdown(wait=True, cancel_futures=True)
        with self._lock:
            self._cancels.clear()  # what is left was queued and never started
        self.fail_interrupted("The server stopped before the run started.")

    # --- monthly budget and visitor quota

    def _fits(self, runs: int) -> bool:
        """Would this many new runs fit this month's budget with their reserves?"""
        b = self.budget
        spent = self.store.spent_since(month_start(self.store.now()))
        return (
            spent.model_usd + b.run_model_usd * runs <= b.model_usd
            and spent.search_credits + b.run_search_credits * runs <= b.search_credits
        )

    def budget_status(self) -> BudgetStatus:
        now = self.store.now()
        spent = self.store.spent_since(month_start(now))
        return BudgetStatus(
            model_usd=self.budget.model_usd,
            spent_model_usd=spent.model_usd,
            search_credits=self.budget.search_credits,
            spent_search_credits=spent.search_credits,
            paused=not self._fits(1),
            resets_at=next_month(now).isoformat(timespec="seconds"),
        )

    def _quota_windows(self, client: str) -> list[tuple[int, timedelta, list[datetime]]]:
        """(limit, window, start times of the client's runs within it) for each quota window."""
        now = self.store.now()
        windows = [(self.quota.per_day, timedelta(days=1)), (self.quota.per_month, timedelta(days=30))]
        return [(limit, window, self.store.run_times(client, since=now - window)) for limit, window in windows]

    def visitor_status(self, client: str) -> VisitorStatus:
        (per_day, _, today), (per_month, _, month) = windows = self._quota_windows(client)
        frees = [times[-limit] + window for limit, window, times in windows if len(times) >= limit]
        return VisitorStatus(
            runs_per_day=per_day,
            runs_today=len(today),
            runs_per_month=per_month,
            runs_this_month=len(month),
            running=self.store.count_running(client) > 0,
            next_run_at=max(frees).isoformat(timespec="seconds") if frees else None,
        )

    def _check_call(self, kind: CallKind) -> None:
        """Before each paid call: stop the run once this month's budget is spent."""
        spent = self.store.spent_since(month_start(self.store.now()))
        if spent.model_usd >= self.budget.model_usd:
            raise BudgetExhausted
        if kind == "search" and spent.search_credits + 1 > self.budget.search_credits:
            raise BudgetExhausted

    def _check_limits(self, client: str) -> None:
        if self.store.count_running(client) > 0:
            raise RunLimitError("A run from your address is already in progress. Wait for it or cancel it.")
        now = self.store.now()
        if not self._fits(1):
            resume = next_month(now)
            raise RunLimitError(
                f"The service is paused by the developer until {month_day(resume)}: "
                "this month's demo budget is used up.",
                retry_after=max(1, math.ceil((resume - now).total_seconds())),
            )
        for (limit, window, times), period in zip(self._quota_windows(client), ("today", "this month")):
            if len(times) >= limit:
                wait = (times[-limit] + window - now).total_seconds()
                raise RunLimitError(
                    f"You have used your {limit} runs for {period}. The next one is available in {wait_text(wait)}.",
                    retry_after=max(1, math.ceil(wait)),
                )
        if not self._fits(self.store.count_all_running() + 1):  # only runs in progress are in the way
            raise RunLimitError("The service is busy right now. Try again in a few minutes.", retry_after=60)

    # --- runs

    def start(self, brief: Brief, client: str) -> str:
        """Start a run or raise RunLimitError: one run at a time and the visitor quota per client,
        within the service's monthly budget."""
        run_id = uuid4().hex
        cancel = threading.Event()
        with self._start_lock:
            self._check_limits(client)
            self.store.create_run(run_id, brief, client)
        with self._lock:
            self._cancels[run_id] = cancel
        self._executor.submit(self._execute, run_id, brief, cancel)
        return run_id

    def cancel(self, run_id: str) -> bool:
        """Ask a running run to stop; False if it is not running in this process."""
        with self._lock:
            cancel = self._cancels.get(run_id)
        if cancel is None:
            return False
        cancel.set()
        return True

    def _execute(self, run_id: str, brief: Brief, cancel: threading.Event) -> None:
        final: list[dict] = []

        def on_event(event: dict) -> None:
            if event["type"] in TERMINAL_EVENTS:
                final.append(event)  # stored together with the result, see Store.finish_run
                return
            self.store.add_event(event)
            self._notify(run_id)

        def on_record(call: LLMCall | SearchCall) -> None:
            if isinstance(call, LLMCall):
                self.store.add_llm_call(run_id, call)
            else:
                self.store.add_search_call(run_id, call)

        try:
            ctx = self._make_context(brief, cancel)
            ctx.before_call, ctx.on_record = self._check_call, on_record
            result = run_sdr(brief, ctx, run_id=run_id, on_event=on_event)
            self.store.finish_run(result, final[-1] if final else None)
        except Exception as error:  # the runner reports graph errors itself; this is infrastructure
            log.exception("run %s crashed outside the graph", run_id)
            self._fail(run_id, f"{type(error).__name__}: {error}")
        finally:
            with self._lock:
                self._cancels.pop(run_id, None)
            self._notify(run_id)

    def _fail(self, run_id: str, message: str) -> None:
        record = self.store.get_run(run_id)
        if record is None:
            return
        events, sequence = [], record.last_sequence + 1
        if sequence == 0:  # the client only follows a run that has started
            started = Started(company=record.brief.company, recipient=record.brief.recipient)
            events.append(to_wire(started, run_id, sequence))
            sequence += 1
        failed = Failed(reason="error", message=PUBLIC_CRASH_MESSAGE, stage=None)
        events.append(to_wire(failed, run_id, sequence))
        self.store.fail_run(run_id, message, events)
        self._notify(run_id)

    # --- stream wake-ups

    @contextmanager
    def subscribe(self, run_id: str) -> Iterator[asyncio.Event]:
        """An asyncio.Event set whenever the run gets new events; call from the event loop."""
        listener = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            self._listeners.setdefault(run_id, set()).add(listener)
        try:
            yield listener[1]
        finally:
            with self._lock:
                listeners = self._listeners.get(run_id, set())
                listeners.discard(listener)
                if not listeners:
                    self._listeners.pop(run_id, None)

    def _notify(self, run_id: str) -> None:
        with self._lock:
            listeners = list(self._listeners.get(run_id, ()))
        for loop, wake in listeners:
            try:
                loop.call_soon_threadsafe(wake.set)
            except RuntimeError:  # loop already closed
                pass
