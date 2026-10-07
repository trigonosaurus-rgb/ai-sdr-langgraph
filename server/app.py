"""HTTP API: start a run, follow its events over SSE, cancel it, restore it after a reload.

uvicorn server.app:app --port 8000
"""

import asyncio
import hashlib
import hmac
import os
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from core.config import Settings
from core.context import RunContext
from core.llm import OpenAILLM
from core.schemas import Brief
from core.search import TavilySearch
from server.runs import BudgetStatus, MonthlyBudget, RunLimitError, RunManager, VisitorQuota, VisitorStatus
from server.store import TERMINAL_EVENTS, LLMCallCost, RunRecord, SearchCallCost, Store, UsageTotals

WAKE_TIMEOUT_S = 15  # re-check the store even without a wake-up
PERIODS = {"24h": timedelta(hours=24), "30d": timedelta(days=30)}


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunCreated(ApiModel):
    run_id: str


class RunSnapshot(ApiModel):
    """What a reloaded page needs to resume: the brief, the status and how far the event log goes.
    The view state itself is rebuilt by replaying events from the stream."""

    run_id: str
    status: str
    reason: str | None
    brief: Brief
    created_at: str
    finished_at: str | None
    last_sequence: int


class CancelAccepted(ApiModel):
    run_id: str


class RunCost(ApiModel):
    """Usage and estimated cost of one run, with every paid call it made, failed ones included."""

    run_id: str
    status: str
    totals: UsageTotals
    llm_calls: list[LLMCallCost]
    search_calls: list[SearchCallCost]


class ServiceStatus(ApiModel):
    """Whether the caller can start a run now: the service's monthly budget and their own quota."""

    paused: bool  # visitors cannot start runs
    developer: bool  # the caller is the developer: no limits apply
    visitor: VisitorStatus


class PeriodUsage(ApiModel):
    """The caller's runs started within the period, and the service's budget this month."""

    period: Literal["24h", "30d"]
    since: str
    totals: UsageTotals
    budget: BudgetStatus


def default_manager() -> RunManager:
    """Production wiring from the environment; fails fast if a provider key is missing."""
    load_dotenv()
    for key in ("OPENAI_API_KEY", "TAVILY_API_KEY"):
        if not os.getenv(key):
            raise RuntimeError(f"{key} is not set")
    settings = Settings.from_env()
    store = Store(os.getenv("SDR_DB_PATH") or "data/sdr.sqlite3")

    def make_context(brief: Brief, cancel: threading.Event) -> RunContext:
        return RunContext(settings=settings, llm=OpenAILLM(settings), search_client=TavilySearch(), cancel=cancel)

    return RunManager(
        store,
        make_context,
        max_workers=int(os.getenv("SDR_MAX_CONCURRENT_RUNS") or 4),
        quota=VisitorQuota(
            per_day=int(os.getenv("SDR_RUNS_PER_DAY") or VisitorQuota.per_day),
            per_month=int(os.getenv("SDR_RUNS_PER_MONTH") or VisitorQuota.per_month),
        ),
        budget=MonthlyBudget(
            model_usd=float(os.getenv("SDR_MONTHLY_MODEL_USD") or MonthlyBudget.model_usd),
            search_credits=float(os.getenv("SDR_MONTHLY_SEARCH_CREDITS") or MonthlyBudget.search_credits),
        ),
    )


def client_id(request: Request) -> str:
    """Salted hash of the client address: enough for per-address limits without storing the address."""
    host = request.client.host if request.client else "unknown"
    salt = os.getenv("SDR_CLIENT_SALT", "")
    return hashlib.sha256(f"{salt}:{host}".encode()).hexdigest()[:32]


def is_developer(key: str | None) -> bool:
    """The developer is recognised by SDR_DEVELOPER_KEY, sent as X-Developer-Key; unset means nobody."""
    expected = os.getenv("SDR_DEVELOPER_KEY", "")
    return bool(expected and key) and hmac.compare_digest(key.encode(), expected.encode())


def create_app(make_manager: Callable[[], RunManager] = default_manager) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        manager = make_manager()
        manager.fail_interrupted("The server restarted during the run.")
        app.state.manager = manager
        yield
        await asyncio.to_thread(manager.shutdown)

    app = FastAPI(title="AI SDR", lifespan=lifespan)

    def get_manager(request: Request) -> RunManager:
        return request.app.state.manager

    Manager = Annotated[RunManager, Depends(get_manager)]

    def get_run(run_id: str, manager: Manager) -> RunRecord:
        record = manager.store.get_run(run_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
        return record

    Run = Annotated[RunRecord, Depends(get_run)]
    DeveloperKey = Annotated[str | None, Header(alias="X-Developer-Key")]

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/status", response_model=ServiceStatus)
    def read_status(request: Request, manager: Manager, developer_key: DeveloperKey = None) -> ServiceStatus:
        return ServiceStatus(
            paused=manager.budget_status().paused,
            developer=is_developer(developer_key),
            visitor=manager.visitor_status(client_id(request)),
        )

    @app.post(
        "/api/runs",
        status_code=status.HTTP_201_CREATED,
        response_model=RunCreated,
        responses={429: {"description": "A run is in progress, the visitor quota is used or the service is paused"}},
    )
    def create_run(
        brief: Brief, request: Request, manager: Manager, developer_key: DeveloperKey = None
    ) -> RunCreated:
        try:
            return RunCreated(
                run_id=manager.start(brief, client_id(request), developer=is_developer(developer_key))
            )
        except RunLimitError as error:
            headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(error), headers=headers) from error

    @app.get("/api/runs/{run_id}", response_model=RunSnapshot)
    def read_run(run: Run) -> RunSnapshot:
        return RunSnapshot(
            run_id=run.id,
            status=run.status,
            reason=run.reason,
            brief=run.brief,
            created_at=run.created_at,
            finished_at=run.finished_at,
            last_sequence=run.last_sequence,
        )

    @app.get("/api/runs/{run_id}/usage", response_model=RunCost)
    def read_run_usage(run: Run, manager: Manager) -> RunCost:
        """Grows while the run is in progress: each paid call is stored as soon as it ends."""
        llm_calls, search_calls = manager.store.run_calls(run.id)
        return RunCost(
            run_id=run.id,
            status=run.status,
            totals=manager.store.usage(run_id=run.id),
            llm_calls=llm_calls,
            search_calls=search_calls,
        )

    @app.get("/api/usage", response_model=PeriodUsage)
    def read_usage(period: Literal["24h", "30d"], request: Request, manager: Manager) -> PeriodUsage:
        since = manager.store.now() - PERIODS[period]
        return PeriodUsage(
            period=period,
            since=since.isoformat(timespec="seconds"),
            totals=manager.store.usage(client=client_id(request), since=since),
            budget=manager.budget_status(),
        )

    @app.post("/api/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED, response_model=CancelAccepted)
    def cancel_run(run: Run, manager: Manager) -> CancelAccepted:
        """Accepted, not done: the stream confirms with a `failed` event whose reason is `cancelled`,
        or with the normal outcome if the last paid call had already finished."""
        if not manager.cancel(run.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "Run is not running")
        return CancelAccepted(run_id=run.id)

    @app.get("/api/runs/{run_id}/events", response_class=EventSourceResponse)
    async def run_events(
        run: Run,
        manager: Manager,
        after: Annotated[int, Query(ge=-1)] = -1,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> AsyncIterator[ServerSentEvent]:
        """Events with sequence > after (or > Last-Event-ID on an automatic reconnect), then live ones.
        The stream ends after `completed` or `failed`; the client should close it then."""
        cursor = int(last_event_id) if last_event_id and last_event_id.lstrip("-").isdigit() else after
        store = manager.store
        with manager.subscribe(run.id) as wake:
            while True:
                wake.clear()  # before reading, so an event stored meanwhile still wakes us
                events = store.events_after(run.id, cursor)
                for sequence, kind, data in events:
                    yield ServerSentEvent(raw_data=data, id=str(sequence))
                    cursor = sequence
                    if kind in TERMINAL_EVENTS:
                        return
                if not events and (current := store.get_run(run.id)) and current.status != "running":
                    return  # finished and fully delivered before this request
                try:
                    await asyncio.wait_for(wake.wait(), WAKE_TIMEOUT_S)
                except TimeoutError:
                    pass

    return app


app = create_app()
