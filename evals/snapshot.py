"""Search snapshots: each case's searches are recorded once and replayed, so every model
configuration works from the same sources. Recording spends PAID Tavily credits.

python -m evals.snapshot [--split all] [--cases linear,stripe] [--force]
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from agents.researcher import search_queries
from core.config import Settings
from core.schemas import Brief, SearchResult
from core.search import SearchClient, SearchResponse, TavilySearch, Topic
from evals.cases import EVALS_DIR, Case, load_cases, select

SNAPSHOTS_DIR = EVALS_DIR / "snapshots"


class SnapshotMissing(LookupError):
    """The run asked for a search the snapshot does not hold: the queries changed, re-record."""


class RecordedSearch(BaseModel):
    query: str
    topic: Topic
    include_domains: list[str] | None
    max_results: int
    credits: float | None
    results: list[SearchResult]

    def matches(self, query: str, topic: str, include_domains: list[str] | None, max_results: int) -> bool:
        return (self.query, self.topic, self.include_domains, self.max_results) == (
            query,
            topic,
            include_domains,
            max_results,
        )


class Snapshot(BaseModel):
    case_id: str
    brief: Brief
    recorded_at: str
    searches: list[RecordedSearch]


def snapshot_path(case_id: str, directory: Path = SNAPSHOTS_DIR) -> Path:
    return directory / f"{case_id}.json"


def record(case: Case, client: SearchClient, settings: Settings) -> Snapshot:
    """Run the researcher's queries for the case and keep every response as it came."""
    searches = []
    for query, options in search_queries(case.brief):
        topic = options.get("topic", "general")
        include_domains = options.get("include_domains")
        max_results = settings.search_results_per_query
        response = client.search(query, topic=topic, include_domains=include_domains, max_results=max_results)
        searches.append(
            RecordedSearch(
                query=query,
                topic=topic,
                include_domains=include_domains,
                max_results=max_results,
                credits=response.credits,
                results=response.results,
            )
        )
    return Snapshot(
        case_id=case.id,
        brief=case.brief,
        recorded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        searches=searches,
    )


def save(snapshot: Snapshot, directory: Path = SNAPSHOTS_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(snapshot.case_id, directory)
    path.write_text(snapshot.model_dump_json(indent=2, exclude={"brief": {"domain"}}) + "\n", encoding="utf-8")
    return path


def load(case: Case, directory: Path = SNAPSHOTS_DIR) -> Snapshot:
    path = snapshot_path(case.id, directory)
    if not path.exists():
        raise SnapshotMissing(f"no search snapshot for {case.id}; record it with python -m evals.snapshot")
    snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
    if snapshot.brief.model_dump() != case.brief.model_dump():
        raise SnapshotMissing(f"the brief of {case.id} changed since its snapshot; re-record it")
    return snapshot


class SnapshotSearch:
    """A SearchClient that answers from a snapshot and reports the credits recorded with it."""

    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.missing: list[str] = []  # the runner turns a miss into a failed run; callers must check this

    def search(
        self,
        query: str,
        *,
        topic: Topic = "general",
        include_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> SearchResponse:
        for recorded in self.snapshot.searches:
            if recorded.matches(query, topic, include_domains, max_results):
                return SearchResponse(results=recorded.results, credits=recorded.credits)
        self.missing.append(query)
        raise SnapshotMissing(f"{self.snapshot.case_id}: no recorded search for {query!r} ({topic})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record search snapshots for evaluation cases (paid Tavily credits).")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="all")
    parser.add_argument("--cases", help="comma-separated case ids")
    parser.add_argument("--force", action="store_true", help="re-record existing snapshots")
    args = parser.parse_args()

    cases = select(load_cases(), args.split, args.cases.split(",") if args.cases else None)
    todo = [case for case in cases if args.force or not snapshot_path(case.id).exists()]
    if not todo:
        print("All snapshots exist; use --force to re-record.", file=sys.stderr)
        return 0

    load_dotenv()
    client, settings = TavilySearch(), Settings()
    credits = 0.0
    for case in todo:
        snapshot = record(case, client, settings)
        save(snapshot)
        spent = sum(search.credits or 0 for search in snapshot.searches)
        credits += spent
        found = [len(search.results) for search in snapshot.searches]
        print(f"{case.id}: results per query {found}, {spent:g} credits", file=sys.stderr)
    print(f"Recorded {len(todo)} snapshots, {credits:g} Tavily credits.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
