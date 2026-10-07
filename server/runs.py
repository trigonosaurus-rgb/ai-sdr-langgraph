"""Runs graphs in worker threads, persists their events and wakes the SSE streams that follow them."""

import asyncio
import logging
import math
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

from core.context import RunContext
from core.events import Failed, Started, to_wire
from core.runner import run_sdr
from core.schemas import Brief
from server.store import TERMINAL_EVENTS, Store

log = logging.getLogger(__name__)
ContextFactory = Callable[[Brief, threading.Event], RunContext]
Listener = tuple[asyncio.AbstractEventLoop, asyncio.Event]

PUBLIC_CRASH_MESSAGE = "The run stopped unexpectedly. Nothing was finished."
LIMIT_WINDOW = timedelta(hours=1)


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
        runs_per_hour: int = 5,
    ):
        self.store = store
        self.runs_per_hour = runs_per_hour
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

    # --- runs

    def _check_limits(self, client: str) -> None:
        if self.store.count_running(client) > 0:
            raise RunLimitError("A run from your address is already in progress. Wait for it or cancel it.")
        now = self.store.now()
        recent = self.store.run_times(client, since=now - LIMIT_WINDOW)
        if len(recent) >= self.runs_per_hour:
            frees_at = recent[-self.runs_per_hour] + LIMIT_WINDOW
            retry_after = max(1, math.ceil((frees_at - now).total_seconds()))
            raise RunLimitError(
                f"Limit reached: {self.runs_per_hour} runs per hour. Try again in {math.ceil(retry_after / 60)} min.",
                retry_after=retry_after,
            )

    def start(self, brief: Brief, client: str) -> str:
        """Start a run or raise RunLimitError: one run at a time and runs_per_hour per client."""
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

        try:
            result = run_sdr(brief, self._make_context(brief, cancel), run_id=run_id, on_event=on_event)
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
