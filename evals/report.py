"""Summarize evaluation results as a Markdown table, one row per results folder.

python -m evals.report [mini luna sol]   # folder names under evals/results; all by default
"""

import argparse
import statistics
import sys
from pathlib import Path

from pydantic import BaseModel

from core.runner import summarize_usage
from evals.cases import load_cases
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
    ungrounded_numbers: int  # drafts with at least one
    model_usd: float | None  # total over all runs; None if any call is unpriced
    median_s: float
    p90_s: float

    @property
    def usd_per_ready(self) -> float | None:
        return None if self.model_usd is None or not self.ready else self.model_usd / self.ready


def load_runs(directory: Path) -> list[CaseRun]:
    return [CaseRun.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]


def summarize(name: str, runs: list[CaseRun], expected_draft: set[str]) -> Row:
    usages = [summarize_usage(r.result.llm_calls, r.result.search_calls, r.result.duration_ms) for r in runs]
    model_costs = [u.model_usd for u in usages]
    seconds = sorted(r.result.duration_ms / 1000 for r in runs)
    draft_runs = [r for r in runs if r.case_id in expected_draft]
    with_draft = [r for r in runs if r.checks.has_draft]
    return Row(
        name=name,
        models=runs[0].models,
        runs=len(runs),
        outcome_ok=sum(r.checks.outcome_ok for r in runs),
        drafts_expected=len(draft_runs),
        ready=sum(r.result.status == "ready" for r in draft_runs),
        draft_checks_ok=sum(bool(r.checks.draft_ok) for r in with_draft),
        drafts=len(with_draft),
        ungrounded_numbers=sum(bool(r.checks.ungrounded_numbers) for r in with_draft),
        model_usd=None if None in model_costs else sum(model_costs),  # type: ignore[arg-type]
        median_s=statistics.median(seconds),
        p90_s=seconds[min(len(seconds) - 1, round(0.9 * (len(seconds) - 1)))],
    )


def usd(value: float | None, digits: int = 4) -> str:
    return "—" if value is None else f"${value:.{digits}f}"


def table(rows: list[Row]) -> str:
    lines = [
        "| Config | Runs | Outcome as expected | Ready (draft cases) | Draft checks pass | Ungrounded numbers"
        " | Model $ / run | Model $ / ready | Median s | p90 s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        per_run = None if row.model_usd is None else row.model_usd / row.runs
        lines.append(
            f"| {row.name} | {row.runs} | {row.outcome_ok}/{row.runs} | {row.ready}/{row.drafts_expected}"
            f" | {row.draft_checks_ok}/{row.drafts} | {row.ungrounded_numbers}/{row.drafts}"
            f" | {usd(per_run)} | {usd(row.usd_per_ready)} | {row.median_s:.0f} | {row.p90_s:.0f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize evaluation results.")
    parser.add_argument("names", nargs="*", help="results folders; all by default")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")

    names = args.names or sorted(p.name for p in RESULTS_DIR.glob("*") if p.is_dir())
    expected_draft = {case.id for case in load_cases() if case.expect == ["draft"]}
    rows = []
    for name in names:
        runs = load_runs(RESULTS_DIR / name)
        if runs:
            rows.append(summarize(name, runs, expected_draft))
    if not rows:
        print("No results yet: python -m evals.run --config <name>", file=sys.stderr)
        return 1
    print(table(rows))
    print("\nModels per config:\n" + "\n".join(f"- {row.name}: {row.models}" for row in rows))
    print("\nCosts are estimates from list prices; searches are replayed from snapshots and not counted here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
