"""HTTP API on a fake graph: start, stream, replay, cancel, restore, crash handling."""

import json
import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from core.context import RunContext
from core.pricing import PRICES, ModelPrice, PriceTable
from core.schemas import Brief, LLMCall, SearchCall, Usage
from server.app import create_app
from server.runs import PAUSED_MESSAGE, PUBLIC_CRASH_MESSAGE, MonthlyBudget, RunLimitError, RunManager, VisitorQuota
from server.store import MIGRATIONS, Store
from fakes import PASS, FakeClock, FakeLLM, draft, happy_script, reject

BRIEF = {
    "company": "Acme",
    "website": "acme.com",
    "offer": "Data engineering contractors for analytics teams",
    "recipient": "VP of Engineering",
    "language": "English",
    "tone": "Direct",
}


class GatedLLM(FakeLLM):
    """Blocks inside the Research call until released, so a test can act on a run in progress."""

    def __init__(self, script):
        super().__init__(script)
        self.entered, self.release = threading.Event(), threading.Event()

    def generate(self, stage, schema, system, user, on_partial=None):
        if stage == "Research":
            self.entered.set()
            assert self.release.wait(5), "test never released the gate"
        return super().generate(stage, schema, system, user, on_partial)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "sdr.sqlite3"


@pytest.fixture
def make_client(db_path, search):
    def make(
        llm_factory=lambda: FakeLLM(happy_script()),
        make_context=None,
        quota: VisitorQuota = VisitorQuota(per_day=100, per_month=100),
        now=None,
        budget: MonthlyBudget = MonthlyBudget(model_usd=100, search_credits=10_000),
        prices: PriceTable = PRICES,
    ) -> TestClient:
        def default_context(brief, cancel: threading.Event) -> RunContext:
            return RunContext(
                settings=Settings(),
                llm=llm_factory(),
                search_client=search,
                clock=FakeClock(),
                cancel=cancel,
                prices=prices,
            )

        def make_manager() -> RunManager:
            store = Store(db_path, now=now) if now else Store(db_path)
            return RunManager(store, make_context or default_context, quota=quota, budget=budget)

        app = create_app(make_manager)
        return TestClient(app)

    return make


def read_events(client: TestClient, run_id: str, **kwargs) -> list[dict]:
    """Read the SSE stream to its end; each event's `id` must match its sequence."""
    events, block = [], {}
    with client.stream("GET", f"/api/runs/{run_id}/events", timeout=10, **kwargs) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line:
                name, _, value = line.partition(": ")
                block[name] = value
                continue
            if "data" in block:  # a blank line ends the event; keep-alive comments have no data
                event = json.loads(block["data"])
                assert event["sequence"] == int(block["id"])
                events.append(event)
            block = {}
    return events


def start(client: TestClient, brief: dict = BRIEF) -> str:
    response = client.post("/api/runs", json=brief)
    assert response.status_code == 201, response.text
    return response.json()["runId"]


def test_full_run_streams_ordered_events_and_snapshot_matches(make_client):
    with make_client() as client:
        run_id = start(client)
        events = read_events(client, run_id)
        snapshot = client.get(f"/api/runs/{run_id}").json()

    assert [e["sequence"] for e in events] == list(range(len(events)))
    assert {e["runId"] for e in events} == {run_id}
    assert events[0]["type"] == "started" and events[-1]["type"] == "completed"
    assert events[-1]["outcome"] == "ready"
    assert snapshot["status"] == "ready" and snapshot["lastSequence"] == events[-1]["sequence"]
    assert snapshot["brief"]["company"] == "Acme" and snapshot["finishedAt"]


def test_replay_starts_after_the_given_sequence(make_client):
    with make_client() as client:
        run_id = start(client)
        full = read_events(client, run_id)
        tail = read_events(client, run_id, params={"after": 5})
        resumed = read_events(client, run_id, params={"after": 0}, headers={"Last-Event-ID": "9"})
        done = read_events(client, run_id, params={"after": full[-1]["sequence"]})

    assert tail == full[6:]
    assert resumed == full[10:]  # Last-Event-ID wins: it is what EventSource sends on reconnect
    assert done == []  # finished and delivered: the stream ends at once


def test_paid_calls_are_stored(make_client, db_path):
    with make_client() as client:
        run_id = start(client)
        read_events(client, run_id)

    store = Store(db_path)
    result = store.get_result(run_id)
    assert result.status == "ready" and len(result.llm_calls) == 4
    with store._lock:
        llm_rows = store._db.execute("SELECT stage, input_tokens FROM llm_calls WHERE run_id = ?", (run_id,)).fetchall()
        search_rows = store._db.execute("SELECT credits FROM search_calls WHERE run_id = ?", (run_id,)).fetchall()
    assert [tuple(r) for r in llm_rows] == [("Research", 100), ("Strategy", 100), ("Writing", 100), ("Review", 100)]
    assert [r[0] for r in search_rows] == [1.0, 1.0, 1.0]


@pytest.mark.parametrize(
    "change",
    [
        {"company": ""},
        {"website": "not a domain"},
        {"language": "German"},
        {"unexpected": "field"},
        {"offer": "x" * 2001},
    ],
)
def test_invalid_brief_is_rejected(make_client, change):
    with make_client() as client:
        response = client.post("/api/runs", json={**BRIEF, **change})
    assert response.status_code == 422


def test_unknown_run_is_404(make_client):
    with make_client() as client:
        assert client.get("/api/runs/nope").status_code == 404
        assert client.get("/api/runs/nope/events").status_code == 404
        assert client.post("/api/runs/nope/cancel").status_code == 404


def test_cancel_is_acknowledged_in_the_stream(make_client):
    llm = GatedLLM(happy_script())
    with make_client(llm_factory=lambda: llm) as client:
        run_id = start(client)
        assert llm.entered.wait(5)
        assert client.post(f"/api/runs/{run_id}/cancel").status_code == 202
        llm.release.set()
        events = read_events(client, run_id)
        snapshot = client.get(f"/api/runs/{run_id}").json()
        again = client.post(f"/api/runs/{run_id}/cancel")

    assert events[-1]["type"] == "failed" and events[-1]["reason"] == "cancelled"
    assert llm.stages() == ["Research"]  # nothing paid after the cancel
    assert snapshot["status"] == "failed" and snapshot["reason"] == "cancelled"
    assert again.status_code == 409


def test_runs_left_running_by_a_previous_process_fail_on_startup(make_client, db_path):
    store = Store(db_path)
    store.create_run("orphan", Brief(**BRIEF), "client")
    store.close()

    with make_client() as client:
        snapshot = client.get("/api/runs/orphan").json()
        events = read_events(client, "orphan")

    assert snapshot["status"] == "failed"
    assert [e["type"] for e in events] == ["started", "failed"]
    assert events[-1]["message"] == PUBLIC_CRASH_MESSAGE


def test_crash_outside_the_graph_still_ends_the_stream(make_client):
    def broken_context(brief, cancel):
        raise RuntimeError("TAVILY_API_KEY rejected")

    with make_client(make_context=broken_context) as client:
        run_id = start(client)
        events = read_events(client, run_id)
        snapshot = client.get(f"/api/runs/{run_id}").json()

    assert [e["type"] for e in events] == ["started", "failed"]
    assert "TAVILY" not in events[-1]["message"]  # details stay on the server
    assert snapshot["status"] == "failed"


def test_migrations_apply_once(db_path):
    Store(db_path).close()
    store = Store(db_path)
    assert store.schema_version == len(MIGRATIONS)


def test_one_run_at_a_time_per_address(make_client):
    llm = GatedLLM(happy_script())
    with make_client(llm_factory=lambda: llm) as client:
        first = start(client)
        assert llm.entered.wait(5)
        busy = client.post("/api/runs", json=BRIEF)
        llm.release.set()
        read_events(client, first)
        after = client.post("/api/runs", json=BRIEF)

    assert busy.status_code == 429 and "already in progress" in busy.json()["detail"]
    assert "retry-after" not in busy.headers
    assert after.status_code == 201


def test_daily_quota_per_address(make_client):
    clock = {"now": datetime(2026, 10, 7, 12, 0, tzinfo=UTC)}
    with make_client(quota=VisitorQuota(per_day=2, per_month=10), now=lambda: clock["now"]) as client:
        for minutes in (0, 10):
            clock["now"] = datetime(2026, 10, 7, 12, minutes, tzinfo=UTC)
            read_events(client, start(client))
        clock["now"] += timedelta(minutes=5)
        limited = client.post("/api/runs", json=BRIEF)
        status = client.get("/api/status").json()
        clock["now"] = datetime(2026, 10, 8, 12, 0, 1, tzinfo=UTC)  # the first run left the window
        allowed = client.post("/api/runs", json=BRIEF)

    assert limited.status_code == 429
    assert limited.json()["detail"] == "You have used your 2 runs for today. The next one is available in 24 h."
    assert limited.headers["retry-after"] == str(23 * 3600 + 45 * 60)
    assert status["visitor"] == {
        "runsPerDay": 2,
        "runsToday": 2,
        "runsPerMonth": 10,
        "runsThisMonth": 2,
        "running": False,
        "nextRunAt": "2026-10-08T12:00:00+00:00",
    }
    assert not status["paused"]
    assert allowed.status_code == 201


def test_monthly_quota_per_address(make_client):
    clock = {"now": datetime(2026, 10, 1, 9, 0, tzinfo=UTC)}
    with make_client(quota=VisitorQuota(per_day=10, per_month=2), now=lambda: clock["now"]) as client:
        read_events(client, start(client))
        clock["now"] += timedelta(days=5)
        read_events(client, start(client))
        clock["now"] += timedelta(days=1)
        limited = client.post("/api/runs", json=BRIEF)
        next_run = client.get("/api/status").json()["visitor"]["nextRunAt"]

    assert limited.status_code == 429
    assert limited.json()["detail"] == "You have used your 2 runs for this month. The next one is available in 24 days."
    assert next_run == "2026-10-31T09:00:00+00:00"


# --- usage, costs and the monthly budget

PRICED = PriceTable(
    version="test-1",
    models={"fake-model": ModelPrice(input=1.0, cached_input=0.1, output=10.0)},
    search_credit_usd=0.01,
)
FAKE_CALL_USD = (80 * 1.0 + 20 * 0.1 + 50 * 10.0) / 1_000_000  # FakeLLM usage: 100 in (20 cached), 50 out
NOON = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def seed_run(db_path, run_id: str, client: str, *, credits: float = 0, usd: float = 0, now=lambda: NOON) -> None:
    """A run of another client that spent the given search credits and model money."""
    store = Store(db_path, now=now)
    store.create_run(run_id, Brief(**BRIEF), client)
    search = SearchCall(query="q", topic="general", results=1, credits=credits, duration_ms=1, cost_usd=credits * 0.008)
    store.add_search_call(run_id, search)
    if usd:
        call = LLMCall(
            stage="Research", attempt=1, model="m", prompt_version="p", duration_ms=1, usage=Usage(), cost_usd=usd
        )
        store.add_llm_call(run_id, call)
    store.fail_run(run_id, "seeded", [])
    store.close()


def test_paid_calls_are_stored_while_the_run_is_in_progress(make_client):
    llm = GatedLLM(happy_script())
    with make_client(llm_factory=lambda: llm) as client:
        run_id = start(client)
        assert llm.entered.wait(5)
        during = client.get(f"/api/runs/{run_id}/usage").json()
        llm.release.set()
        read_events(client, run_id)
        after = client.get(f"/api/runs/{run_id}/usage").json()

    assert during["status"] == "running"
    assert len(during["searchCalls"]) == 3 and during["llmCalls"] == []
    assert after["status"] == "ready" and len(after["llmCalls"]) == 4


def test_run_usage_has_totals_and_every_call(make_client):
    script = happy_script(Writing=[draft(1), draft(2)], Review=[reject(), PASS])
    with make_client(llm_factory=lambda: FakeLLM(script), prices=PRICED) as client:
        run_id = start(client)
        events = read_events(client, run_id)
        usage = client.get(f"/api/runs/{run_id}/usage").json()

    totals = usage["totals"]
    assert totals["runs"] == 1 and totals["llmCalls"] == 6 and totals["searchCalls"] == 3
    assert (totals["input"], totals["cachedInput"], totals["output"], totals["reasoning"]) == (600, 120, 300, 60)
    assert totals["modelUsd"] == pytest.approx(6 * FAKE_CALL_USD)
    assert totals["searchCredits"] == 3 and totals["searchUsd"] == pytest.approx(0.03)
    assert totals["priceVersions"] == ["test-1"] and not totals["incomplete"]
    assert totals["durationSeconds"] == events[-1]["usage"]["durationSeconds"]
    stages = [(c["stage"], c["attempt"]) for c in usage["llmCalls"]]
    assert stages == [("Research", 1), ("Strategy", 1), ("Writing", 1), ("Review", 1), ("Writing", 2), ("Review", 2)]
    # the completed event carries the same costs, fixed when the calls were recorded
    assert events[-1]["usage"]["modelUsd"] == pytest.approx(totals["modelUsd"])


def test_unknown_usage_is_a_gap_not_a_zero(make_client):
    with make_client(llm_factory=lambda: FakeLLM(happy_script(), usage=Usage()), prices=PRICED) as client:
        run_id = start(client)
        read_events(client, run_id)
        totals = client.get(f"/api/runs/{run_id}/usage").json()["totals"]

    assert totals["input"] is None and totals["modelUsd"] is None
    assert totals["searchUsd"] == pytest.approx(0.03)  # what is known stays known
    assert totals["incomplete"]


def test_partly_unknown_usage_sums_the_known_part_and_says_so(make_client):
    llms = iter([FakeLLM(happy_script()), FakeLLM(happy_script(), model="unpriced-model")])
    with make_client(llm_factory=lambda: next(llms), prices=PRICED) as client:
        read_events(client, start(client))
        read_events(client, start(client))
        totals = client.get("/api/usage", params={"period": "24h"}).json()["totals"]

    assert totals["runs"] == 2 and totals["input"] == 800  # tokens are known for both
    assert totals["modelUsd"] == pytest.approx(4 * FAKE_CALL_USD)  # only the priced run
    assert totals["incomplete"]
    assert totals["models"] == ["fake-model", "unpriced-model"]


def test_period_usage_counts_only_the_callers_runs_in_the_period(make_client, db_path):
    clock = {"now": NOON - timedelta(days=40)}
    with make_client(now=lambda: clock["now"], prices=PRICED) as client:
        read_events(client, start(client))  # too old for 30 days
        clock["now"] = NOON - timedelta(days=3)
        read_events(client, start(client))  # within 30 days, not 24 hours
        clock["now"] = NOON
        read_events(client, start(client))
        seed_run(db_path, "other", "someone-else", credits=5)
        day = client.get("/api/usage", params={"period": "24h"}).json()
        month = client.get("/api/usage", params={"period": "30d"}).json()
        bad = client.get("/api/usage", params={"period": "1y"})

    assert day["totals"]["runs"] == 1 and day["totals"]["searchCredits"] == 3
    assert month["totals"]["runs"] == 2 and month["totals"]["modelUsd"] == pytest.approx(8 * FAKE_CALL_USD)
    assert day["since"] == "2026-10-06T12:00:00+00:00"
    assert bad.status_code == 422
    # the budget belongs to the service: everyone's spending this month, the other client included;
    # search is counted in credits, money only for the models
    budget = day["budget"]
    assert budget["spentSearchCredits"] == 3 + 3 + 5
    assert budget["spentModelUsd"] == pytest.approx(8 * FAKE_CALL_USD)
    assert budget["resetsAt"] == "2026-11-01T00:00:00+00:00" and not budget["paused"]


def test_no_runs_is_a_real_zero(make_client):
    with make_client() as client:
        totals = client.get("/api/usage", params={"period": "30d"}).json()["totals"]
    assert totals["runs"] == 0 and totals["modelUsd"] == 0 and totals["input"] == 0
    assert not totals["incomplete"]


def test_monthly_search_credits_stop_the_service_for_visitors(make_client, db_path):
    seed_run(db_path, "other", "someone-else", credits=748)
    with make_client(now=lambda: NOON, budget=MonthlyBudget(model_usd=100, search_credits=750)) as client:
        response = client.post("/api/runs", json=BRIEF)
        status = client.get("/api/status").json()

    assert response.status_code == 429
    assert response.json()["detail"] == PAUSED_MESSAGE == "The service is temporarily stopped by the developer."
    assert "retry-after" not in response.headers  # the developer decides when it is back
    assert status["paused"] and not status["developer"]


def test_monthly_model_budget_pauses_the_service(make_client, db_path):
    seed_run(db_path, "other", "someone-else", usd=4.99)
    with make_client(now=lambda: NOON, budget=MonthlyBudget(model_usd=5, run_model_usd=0.05)) as client:
        assert client.post("/api/runs", json=BRIEF).status_code == 429
        assert client.get("/api/status").json()["paused"]


def test_last_months_spending_does_not_count(make_client, db_path):
    seed_run(db_path, "other", "someone-else", usd=10, credits=750, now=lambda: NOON - timedelta(days=30))
    with make_client(now=lambda: NOON, budget=MonthlyBudget(model_usd=5, search_credits=750)) as client:
        assert client.post("/api/runs", json=BRIEF).status_code == 201


def test_runs_in_progress_reserve_their_share_of_the_budget(db_path):
    store = Store(db_path)
    store.create_run("busy", Brief(**BRIEF), "someone-else")  # still running
    manager = RunManager(store, lambda brief, cancel: None, budget=MonthlyBudget(model_usd=0.08, run_model_usd=0.05))
    with pytest.raises(RunLimitError, match="busy right now") as caught:
        manager.start(Brief(**BRIEF), "me")
    assert caught.value.retry_after == 60
    assert not manager.budget_status().paused  # one run alone would still fit
    manager.shutdown()


def test_budget_stops_a_run_before_the_call_that_would_exceed_it(make_client):
    # Each LLM call costs 0.048: Research and Strategy leave 0.004 of 0.10, Writing still starts,
    # and the Review call is refused because the budget is spent.
    expensive = PriceTable(version="test-2", models={"fake-model": ModelPrice(600, 0, 0)}, search_credit_usd=0)
    llm = FakeLLM(happy_script())
    budget = MonthlyBudget(model_usd=0.10, run_model_usd=0.10)
    with make_client(llm_factory=lambda: llm, prices=expensive, budget=budget) as client:
        run_id = start(client)
        events = read_events(client, run_id)
        again = client.post("/api/runs", json=BRIEF)

    assert llm.stages() == ["Research", "Strategy", "Writing"]
    assert events[-1]["type"] == "failed" and events[-1]["reason"] == "budget_exhausted"
    assert "temporarily stopped by the developer" in events[-1]["message"]
    assert events[-1]["stage"] == "Review"
    assert again.status_code == 429 and again.json()["detail"] == PAUSED_MESSAGE


# --- the developer has no limits

DEV = {"X-Developer-Key": "dev-secret"}


@pytest.fixture
def developer_key(monkeypatch):
    monkeypatch.setenv("SDR_DEVELOPER_KEY", "dev-secret")


def test_developer_key_skips_the_visitor_quota(make_client, developer_key):
    with make_client(quota=VisitorQuota(per_day=1, per_month=1)) as client:
        read_events(client, start(client))
        visitor = client.post("/api/runs", json=BRIEF)
        wrong = client.post("/api/runs", json=BRIEF, headers={"X-Developer-Key": "guess"})
        developer = client.post("/api/runs", json=BRIEF, headers=DEV)
        read_events(client, developer.json()["runId"])
        statuses = [client.get("/api/status", headers=h).json()["developer"] for h in ({}, {"X-Developer-Key": "guess"}, DEV)]

    assert visitor.status_code == 429 and wrong.status_code == 429
    assert developer.status_code == 201
    assert statuses == [False, False, True]


def test_developer_runs_while_the_service_is_stopped_and_their_spending_counts(make_client, db_path, developer_key):
    seed_run(db_path, "other", "someone-else", credits=748)
    budget = MonthlyBudget(model_usd=100, search_credits=750)
    with make_client(now=lambda: NOON, budget=budget, prices=PRICED) as client:
        assert client.post("/api/runs", json=BRIEF).status_code == 429
        run_id = client.post("/api/runs", json=BRIEF, headers=DEV).json()["runId"]
        events = read_events(client, run_id)  # not stopped before its paid calls either
        spent = client.get("/api/usage", params={"period": "24h"}).json()["budget"]["spentSearchCredits"]

    assert events[-1]["type"] == "completed"
    assert spent == 748 + 3


def test_without_a_configured_key_nobody_is_the_developer(make_client, monkeypatch):
    monkeypatch.delenv("SDR_DEVELOPER_KEY", raising=False)
    with make_client(quota=VisitorQuota(per_day=1, per_month=1)) as client:
        read_events(client, start(client))
        response = client.post("/api/runs", json=BRIEF, headers={"X-Developer-Key": ""})
        status = client.get("/api/status", headers={"X-Developer-Key": ""}).json()
    assert response.status_code == 429 and not status["developer"]
