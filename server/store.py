"""SQLite storage for runs, their event log and every paid call.

One connection shared across threads behind a lock: the graph runs in worker
threads, the API reads from the event loop, and every statement is short.
"""

import json
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from core.schemas import Brief, LLMCall, RunResult, SearchCall

RunStatus = str  # "running" | "ready" | "needs_attention" | "failed"
TERMINAL_EVENTS = frozenset({"completed", "failed"})

# Append only: each entry moves the schema one version forward (PRAGMA user_version).
MIGRATIONS = [
    """
    CREATE TABLE runs (
        id TEXT PRIMARY KEY,
        client TEXT NOT NULL,            -- salted hash of the client address, for limits
        brief TEXT NOT NULL,             -- JSON
        status TEXT NOT NULL,            -- running | ready | needs_attention | failed
        reason TEXT,                     -- FailureReason when failed
        message TEXT,                    -- internal outcome message, may hold error details
        result TEXT,                     -- RunResult JSON once finished
        created_at TEXT NOT NULL,        -- ISO 8601 UTC
        finished_at TEXT
    );
    CREATE INDEX runs_client_created ON runs (client, created_at);
    CREATE INDEX runs_status ON runs (status);

    CREATE TABLE events (
        run_id TEXT NOT NULL REFERENCES runs (id),
        sequence INTEGER NOT NULL,
        type TEXT NOT NULL,
        data TEXT NOT NULL,              -- the wire event as sent to the client
        created_at TEXT NOT NULL,
        PRIMARY KEY (run_id, sequence)
    );

    CREATE TABLE llm_calls (
        id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs (id),
        stage TEXT NOT NULL,
        attempt INTEGER NOT NULL,
        model TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        input_tokens INTEGER,            -- NULL: not reported by the API
        cached_input_tokens INTEGER,
        output_tokens INTEGER,
        reasoning_tokens INTEGER,
        error TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX llm_calls_run ON llm_calls (run_id);

    CREATE TABLE search_calls (
        id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs (id),
        query TEXT NOT NULL,
        topic TEXT NOT NULL,
        results INTEGER NOT NULL,
        credits REAL,                    -- NULL: not reported by the provider
        duration_ms INTEGER NOT NULL,
        error TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX search_calls_run ON search_calls (run_id);
    """,
    # Costs are fixed when a call is recorded; calls stored before pricing keep NULL (unknown).
    """
    ALTER TABLE llm_calls ADD COLUMN cost_usd REAL;
    ALTER TABLE llm_calls ADD COLUMN price_version TEXT;
    ALTER TABLE search_calls ADD COLUMN cost_usd REAL;
    ALTER TABLE search_calls ADD COLUMN price_version TEXT;
    CREATE INDEX llm_calls_created ON llm_calls (created_at);
    CREATE INDEX search_calls_created ON search_calls (created_at);
    CREATE INDEX runs_created ON runs (created_at);
    ALTER TABLE runs ADD COLUMN duration_ms INTEGER;
    UPDATE runs SET duration_ms = json_extract(result, '$.duration_ms') WHERE result IS NOT NULL;
    """,
]


class RunRecord(BaseModel):
    id: str
    client: str
    brief: Brief
    status: RunStatus
    reason: str | None
    created_at: str
    finished_at: str | None
    last_sequence: int  # -1 when no events yet


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UsageTotals(CamelModel):
    """Usage and estimated cost of a set of runs. Each total sums the calls that reported it;
    it is None when calls exist but none reported it, and incomplete is set when some did not."""

    runs: int
    llm_calls: int
    search_calls: int
    input: int | None
    cached_input: int | None  # subset of input
    output: int | None
    reasoning: int | None  # subset of output
    search_credits: float | None
    model_usd: float | None
    search_usd: float | None
    duration_seconds: float | None  # finished runs only
    models: list[str]
    price_versions: list[str]
    incomplete: bool


class LLMCallCost(CamelModel):
    stage: str
    attempt: int
    model: str
    input: int | None
    cached_input: int | None
    output: int | None
    reasoning: int | None
    cost_usd: float | None
    duration_ms: int
    failed: bool


class SearchCallCost(CamelModel):
    topic: str
    results: int
    credits: float | None
    cost_usd: float | None
    duration_ms: int
    failed: bool


class Spend(BaseModel):
    usd: float  # known costs only
    search_credits: float  # a search without reported credits counts as one


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Store:
    def __init__(self, path: str | Path, now: Callable[[], datetime] = _utc_now):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._now = now
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, autocommit=True)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.execute("PRAGMA synchronous = NORMAL")
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def now(self) -> datetime:
        return self._now()

    def _timestamp(self) -> str:
        return self._now().isoformat(timespec="milliseconds")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("COMMIT")

    def _migrate(self) -> None:
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            with self._transaction() as db:
                for statement in script.split(";"):
                    if statement.strip():
                        db.execute(statement)
                db.execute(f"PRAGMA user_version = {number}")

    @property
    def schema_version(self) -> int:
        with self._lock:
            return self._db.execute("PRAGMA user_version").fetchone()[0]

    # --- runs

    def create_run(self, run_id: str, brief: Brief, client: str) -> None:
        with self._transaction() as db:
            db.execute(
                "INSERT INTO runs (id, client, brief, status, created_at) VALUES (?, ?, ?, 'running', ?)",
                (run_id, client, brief.model_dump_json(exclude={"domain"}), self._timestamp()),
            )

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            row = self._db.execute(
                """
                SELECT runs.*, COALESCE(MAX(events.sequence), -1) AS last_sequence
                FROM runs LEFT JOIN events ON events.run_id = runs.id
                WHERE runs.id = ? GROUP BY runs.id
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RunRecord(
            id=row["id"],
            client=row["client"],
            brief=Brief.model_validate_json(row["brief"]),
            status=row["status"],
            reason=row["reason"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
            last_sequence=row["last_sequence"],
        )

    def get_result(self, run_id: str) -> RunResult | None:
        with self._lock:
            row = self._db.execute("SELECT result FROM runs WHERE id = ?", (run_id,)).fetchone()
        return RunResult.model_validate_json(row["result"]) if row and row["result"] else None

    def finish_run(self, result: RunResult, final_event: dict | None) -> None:
        """Record the outcome and its terminal event atomically: a client never sees `completed`
        while the snapshot still says running, or the reverse. Paid calls are stored as they end."""
        with self._transaction() as db:
            if final_event is not None:
                self._insert_event(db, final_event)
            db.execute(
                """
                UPDATE runs SET status = ?, reason = ?, message = ?, result = ?, finished_at = ?, duration_ms = ?
                WHERE id = ?
                """,
                (
                    result.status,
                    result.reason,
                    result.message,
                    result.model_dump_json(exclude={"brief": {"domain"}}),  # computed, rejected on read
                    self._timestamp(),
                    result.duration_ms,
                    result.run_id,
                ),
            )

    def fail_run(self, run_id: str, message: str, events: list[dict]) -> None:
        """Mark a run failed outside the runner (crash, restart) and log the events that say so."""
        with self._transaction() as db:
            db.execute(
                "UPDATE runs SET status = 'failed', reason = 'error', message = ?, finished_at = ? WHERE id = ?",
                (message, self._timestamp(), run_id),
            )
            for event in events:
                self._insert_event(db, event)

    def running_run_ids(self) -> list[str]:
        with self._lock:
            rows = self._db.execute("SELECT id FROM runs WHERE status = 'running'").fetchall()
        return [row["id"] for row in rows]

    def count_running(self, client: str) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM runs WHERE client = ? AND status = 'running'", (client,)
            ).fetchone()[0]

    def run_times(self, client: str, since: datetime) -> list[datetime]:
        """Start times of the client's runs since the given moment, oldest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT created_at FROM runs WHERE client = ? AND created_at >= ? ORDER BY created_at",
                (client, since.isoformat(timespec="milliseconds")),
            ).fetchall()
        return [datetime.fromisoformat(row["created_at"]) for row in rows]

    def count_all_running(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM runs WHERE status = 'running'").fetchone()[0]

    # --- paid calls, stored as soon as each one ends so the spending limits see it at once

    def add_llm_call(self, run_id: str, call: LLMCall) -> None:
        u = call.usage
        with self._transaction() as db:
            db.execute(
                """
                INSERT INTO llm_calls (run_id, stage, attempt, model, prompt_version, duration_ms,
                    input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
                    cost_usd, price_version, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, call.stage, call.attempt, call.model, call.prompt_version, call.duration_ms,
                    u.input_tokens, u.cached_input_tokens, u.output_tokens, u.reasoning_tokens,
                    call.cost_usd, call.price_version, call.error, self._timestamp(),
                ),
            )  # fmt: skip

    def add_search_call(self, run_id: str, call: SearchCall) -> None:
        with self._transaction() as db:
            db.execute(
                """
                INSERT INTO search_calls (run_id, query, topic, results, credits, duration_ms,
                    cost_usd, price_version, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, call.query, call.topic, call.results, call.credits, call.duration_ms,
                    call.cost_usd, call.price_version, call.error, self._timestamp(),
                ),
            )  # fmt: skip

    def spent_since(self, since: datetime) -> Spend:
        """Service-wide spending since the given moment, for the daily limits."""
        stamp = since.isoformat(timespec="milliseconds")
        with self._lock:
            llm_usd = self._db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE created_at >= ?", (stamp,)
            ).fetchone()[0]
            search_usd, credits = self._db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0), COALESCE(SUM(COALESCE(credits, 1)), 0)"
                " FROM search_calls WHERE created_at >= ?",
                (stamp,),
            ).fetchone()
        return Spend(usd=llm_usd + search_usd, search_credits=credits)

    def usage(
        self, *, run_id: str | None = None, client: str | None = None, since: datetime | None = None
    ) -> UsageTotals:
        """Totals for one run, or for a client's runs started since the given moment."""
        if run_id is not None:
            where, params = "runs.id = ?", (run_id,)
        else:
            stamp = since.isoformat(timespec="milliseconds") if since else ""
            where, params = "runs.client = ? AND runs.created_at >= ?", (client, stamp)
        incomplete = False

        def known(total, reported: int, count: int):
            nonlocal incomplete
            incomplete = incomplete or reported < count
            return total if reported else (None if count else 0)

        llm_join = f"FROM llm_calls JOIN runs ON runs.id = llm_calls.run_id WHERE {where}"
        search_join = f"FROM search_calls JOIN runs ON runs.id = search_calls.run_id WHERE {where}"
        with self._lock:
            runs, duration = self._db.execute(
                f"SELECT COUNT(*), SUM(duration_ms) FROM runs WHERE {where}", params
            ).fetchone()
            llm = self._db.execute(
                f"""
                SELECT COUNT(*) AS n,
                    SUM(input_tokens) AS input, COUNT(input_tokens) AS input_n,
                    SUM(cached_input_tokens) AS cached, COUNT(cached_input_tokens) AS cached_n,
                    SUM(output_tokens) AS output, COUNT(output_tokens) AS output_n,
                    SUM(reasoning_tokens) AS reasoning, COUNT(reasoning_tokens) AS reasoning_n,
                    SUM(cost_usd) AS usd, COUNT(cost_usd) AS usd_n
                {llm_join}
                """,
                params,
            ).fetchone()
            search = self._db.execute(
                f"""
                SELECT COUNT(*) AS n, SUM(credits) AS credits, COUNT(credits) AS credits_n,
                    SUM(cost_usd) AS usd, COUNT(cost_usd) AS usd_n
                {search_join}
                """,
                params,
            ).fetchone()
            models = self._db.execute(f"SELECT DISTINCT model {llm_join}", params).fetchall()
            versions = self._db.execute(
                f"SELECT price_version {llm_join} UNION SELECT price_version {search_join}", params + params
            ).fetchall()
        n = llm["n"]
        return UsageTotals(
            runs=runs,
            llm_calls=n,
            search_calls=search["n"],
            input=known(llm["input"], llm["input_n"], n),
            cached_input=known(llm["cached"], llm["cached_n"], n),
            output=known(llm["output"], llm["output_n"], n),
            reasoning=known(llm["reasoning"], llm["reasoning_n"], n),
            model_usd=known(llm["usd"], llm["usd_n"], n),
            search_credits=known(search["credits"], search["credits_n"], search["n"]),
            search_usd=known(search["usd"], search["usd_n"], search["n"]),
            duration_seconds=duration / 1000 if duration is not None else None,
            models=sorted(row[0] for row in models),
            price_versions=sorted(row[0] for row in versions if row[0]),
            incomplete=incomplete,
        )

    def run_calls(self, run_id: str) -> tuple[list[LLMCallCost], list[SearchCallCost]]:
        """Every paid call of a run, in the order it was made."""
        with self._lock:
            llm = self._db.execute(
                """
                SELECT stage, attempt, model, input_tokens AS input, cached_input_tokens AS cached_input,
                    output_tokens AS output, reasoning_tokens AS reasoning, cost_usd, duration_ms,
                    error IS NOT NULL AS failed
                FROM llm_calls WHERE run_id = ? ORDER BY id
                """,
                (run_id,),
            ).fetchall()
            search = self._db.execute(
                """
                SELECT topic, results, credits, cost_usd, duration_ms, error IS NOT NULL AS failed
                FROM search_calls WHERE run_id = ? ORDER BY id
                """,
                (run_id,),
            ).fetchall()
        return [LLMCallCost(**dict(row)) for row in llm], [SearchCallCost(**dict(row)) for row in search]

    # --- events

    def _insert_event(self, db: sqlite3.Connection, event: dict) -> None:
        db.execute(
            "INSERT INTO events (run_id, sequence, type, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                event["runId"],
                event["sequence"],
                event["type"],
                json.dumps(event, ensure_ascii=False, separators=(",", ":")),
                self._timestamp(),
            ),
        )

    def add_event(self, event: dict) -> None:
        with self._transaction() as db:
            self._insert_event(db, event)

    def events_after(self, run_id: str, after: int) -> list[tuple[int, str, str]]:
        """(sequence, type, JSON data) of the run's events with sequence > after, in order."""
        with self._lock:
            rows = self._db.execute(
                "SELECT sequence, type, data FROM events WHERE run_id = ? AND sequence > ? ORDER BY sequence",
                (run_id, after),
            ).fetchall()
        return [(row["sequence"], row["type"], row["data"]) for row in rows]
