"""HTTP API on a fake graph: start, stream, replay, cancel, restore, crash handling."""

import json
import threading

import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from core.context import RunContext
from server.app import create_app
from server.runs import PUBLIC_CRASH_MESSAGE, RunManager
from server.store import MIGRATIONS, Store
from fakes import FakeClock, FakeLLM, happy_script

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
        runs_per_hour: int = 100,
        now=None,
    ) -> TestClient:
        def default_context(brief, cancel: threading.Event) -> RunContext:
            return RunContext(
                settings=Settings(), llm=llm_factory(), search_client=search, clock=FakeClock(), cancel=cancel
            )

        def make_manager() -> RunManager:
            store = Store(db_path, now=now) if now else Store(db_path)
            return RunManager(store, make_context or default_context, runs_per_hour=runs_per_hour)

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
    from core.schemas import Brief

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


def test_hourly_limit_per_address(make_client):
    from datetime import UTC, datetime, timedelta

    clock = {"now": datetime(2026, 10, 7, 12, 0, tzinfo=UTC)}
    with make_client(runs_per_hour=2, now=lambda: clock["now"]) as client:
        for minutes in (0, 10):
            clock["now"] = datetime(2026, 10, 7, 12, minutes, tzinfo=UTC)
            read_events(client, start(client))
        clock["now"] += timedelta(minutes=5)
        limited = client.post("/api/runs", json=BRIEF)
        clock["now"] = datetime(2026, 10, 7, 13, 0, 1, tzinfo=UTC)  # the 12:00 run left the window
        allowed = client.post("/api/runs", json=BRIEF)

    assert limited.status_code == 429 and "2 runs per hour" in limited.json()["detail"]
    assert limited.headers["retry-after"] == str(45 * 60)
    assert allowed.status_code == 201
