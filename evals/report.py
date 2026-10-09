"""Summarize evaluation results as a Markdown table, one row per results folder.

python -m evals.report [mini luna sol] [--grader claude]   # folders under evals/results; all by default

A run succeeds when its outcome is as expected and, if it is a draft, the draft is graded good.
Without grades for every such draft the success count and cost per success stay unknown.
"""

import argparse
import statistics
import sys
from pathlib import Path

from pydantic import BaseModel

from core.runner import summarize_usage
from evals.cases import Case, load_cases
from evals.checks import check
from evals.grades import Grade, load_grades
from evals.run import RESULTS_DIR, CaseRun


class Row(BaseModel):
    name: str
    models: str
    runs: int
    outcome_ok: int
    drafts_expected: int  # runs whose case expects only a draft
    ready: int  # of those, runs that ended ready
    draft_checks_ok: int
    drafts: int
    model_usd: float | None  # total over all runs; None if any call is unpriced
    median_s: float
    p90_s: float
    graded: int  # drafts with a grade
    grounding: float | None  # mean scores of graded drafts
    relevance: float | None
    naturalness: float | None
    successes: int | None  # None until every draft that counts is graded

    @property
    def usd_per_success(self) -> float | None:
        if self.model_usd is None or not self.successes:
            return None
        return self.model_usd / self.successes


def load_runs(directory: Path, cases: dict[str, Case]) -> list[CaseRun]:
    """Saved runs with their checks recomputed, so a fixed check applies to earlier runs too."""
    runs = [CaseRun.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]
    return [run.model_copy(update={"checks": check(cases[run.case_id], run.result)}) for run in runs]


def mean(values: list[int]) -> float | None:
    return statistics.mean(values) if values else None


def summarize(name: str, runs: list[CaseRun], expected_draft: set[str], grades: dict[str, Grade] | None = None) -> Row:
    usages = [summarize_usage(r.result.llm_calls, r.result.search_calls, r.result.duration_ms) for r in runs]
    model_costs = [u.model_usd for u in usages]
    seconds = sorted(r.result.duration_ms / 1000 for r in runs)
    draft_runs = [r for r in runs if r.case_id in expected_draft]
    with_draft = [r for r in runs if r.checks.has_draft]
    grades = grades or {}
    graded = [grades[key] for r in runs if (key := f"{r.case_id}.{r.repeat}") in grades]
    # a draft counts when a draft was the right outcome; poor-fit and wrong drafts are judged by outcome
    to_grade = [f"{r.case_id}.{r.repeat}" for r in runs if r.checks.outcome_ok and r.checks.label == "draft"]
    successes = None
    if all(key in grades for key in to_grade):
        refusals = sum(r.checks.outcome_ok and r.checks.label != "draft" for r in runs)
        successes = refusals + sum(grades[key].good for key in to_grade)
    return Row(
        name=name,
        models=runs[0].models,
        runs=len(runs),
        outcome_ok=sum(r.checks.outcome_ok for r in runs),
        drafts_expected=len(draft_runs),
        ready=sum(r.result.status == "ready" for r in draft_runs),
        draft_checks_ok=sum(bool(r.checks.draft_ok) for r in with_draft),
        drafts=len(with_draft),
        model_usd=None if None in model_costs else sum(model_costs),  # type: ignore[arg-type]
        median_s=statistics.median(seconds),
        p90_s=seconds[min(len(seconds) - 1, round(0.9 * (len(seconds) - 1)))],
        graded=len(graded),
        grounding=mean([g.grounding for g in graded]),
        relevance=mean([g.relevance for g in graded]),
        naturalness=mean([g.naturalness for g in graded]),
        successes=successes,
    )


def usd(value: float | None, digits: int = 4) -> str:
    return "—" if value is None else f"${value:.{digits}f}"


def score(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def table(rows: list[Row]) -> str:
    lines = [
        "| Config | Runs | Outcome as expected | Ready (draft cases) | Draft checks pass | Grounding | Relevance"
        " | Naturalness | Successful | Model $ / run | Model $ / success | Median s | p90 s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        per_run = None if row.model_usd is None else row.model_usd / row.runs
        successes = "—" if row.successes is None else f"{row.successes}/{row.runs}"
        lines.append(
            f"| {row.name} | {row.runs} | {row.outcome_ok}/{row.runs} | {row.ready}/{row.drafts_expected}"
            f" | {row.draft_checks_ok}/{row.drafts} | {score(row.grounding)} | {score(row.relevance)}"
            f" | {score(row.naturalness)} | {successes} | {usd(per_run)} | {usd(row.usd_per_success)}"
            f" | {row.median_s:.0f} | {row.p90_s:.0f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize evaluation results.")
    parser.add_argument("names", nargs="*", help="results folders; all by default")
    parser.add_argument("--grader", default="claude", help="whose grades to use: claude or human")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")

    names = args.names or sorted(p.name for p in RESULTS_DIR.glob("*") if p.is_dir())
    cases = {case.id: case for case in load_cases()}
    expected_draft = {case.id for case in cases.values() if case.expect == ["draft"]}
    rows = []
    for name in names:
        runs = load_runs(RESULTS_DIR / name, cases)
        if runs:
            rows.append(summarize(name, runs, expected_draft, load_grades(name, args.grader)))
    if not rows:
        print("No results yet: python -m evals.run --config <name>", file=sys.stderr)
        return 1
    print(table(rows))
    print("\nModels per config:\n" + "\n".join(f"- {row.name}: {row.models}" for row in rows))
    print(f"\nScores: mean 0-2 by {args.grader} over graded drafts (evals/README.md).")
    print("Costs are estimates from list prices; searches are replayed from snapshots and not counted here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
