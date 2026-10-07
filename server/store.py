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

from pydantic import BaseModel

from core.schemas import Brief, RunResult

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
        """Record the outcome, its terminal event and every paid call of a finished run, atomically:
        a client never sees `completed` while the snapshot still says running, or the reverse."""
        now = self._timestamp()
        with self._transaction() as db:
            if final_event is not None:
                self._insert_event(db, final_event)
            db.execute(
                "UPDATE runs SET status = ?, reason = ?, message = ?, result = ?, finished_at = ? WHERE id = ?",
                (
                    result.status,
                    result.reason,
                    result.message,
                    result.model_dump_json(exclude={"brief": {"domain"}}),  # computed, rejected on read
                    now,
                    result.run_id,
                ),
            )
            db.executemany(
                """
                INSERT INTO llm_calls (run_id, stage, attempt, model, prompt_version, duration_ms,
                    input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        result.run_id, c.stage, c.attempt, c.model, c.prompt_version, c.duration_ms,
                        c.usage.input_tokens, c.usage.cached_input_tokens, c.usage.output_tokens,
                        c.usage.reasoning_tokens, c.error, now,
                    )
                    for c in result.llm_calls
                ],
            )
            db.executemany(
                """
                INSERT INTO search_calls (run_id, query, topic, results, credits, duration_ms, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (result.run_id, c.query, c.topic, c.results, c.credits, c.duration_ms, c.error, now)
                    for c in result.search_calls
                ],
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
