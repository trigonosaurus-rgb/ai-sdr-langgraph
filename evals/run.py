"""Run evaluation cases with one model configuration on recorded search snapshots.
Makes PAID OpenAI calls; searches are replayed, not repeated.

python -m evals.run --config mini [--split dev] [--cases linear,stripe] [--repeat 2] [--name mini-v1]

Results go to evals/results/<name>/<case>.<repeat>.json; existing ones are kept, so an
interrupted run resumes where it stopped.
"""

import argparse
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from core.config import Settings
from core.context import RunContext
from core.llm import OpenAILLM, StructuredLLM
from core.runner import run_sdr, summarize_usage
from core.schemas import RunResult
from evals.cases import EVALS_DIR, Case, load_cases, select
from evals.checks import Checks, check
from evals.configs import CONFIGS, ModelConfig, describe
from evals.snapshot import SNAPSHOTS_DIR, SnapshotMissing, SnapshotSearch, load

RESULTS_DIR = EVALS_DIR / "results"
LLMFactory = Callable[[Settings], StructuredLLM]


class CaseRun(BaseModel):
    case_id: str
    config: str
    models: str  # describe() of the configuration, kept in case the named config changes later
    repeat: int
    snapshot_recorded_at: str
    checks: Checks
    result: RunResult


def result_path(directory: Path, case_id: str, repeat: int) -> Path:
    return directory / f"{case_id}.{repeat}.json"


def save_run(run: CaseRun, path: Path) -> None:
    # the brief's domain is computed and rejected on read, as in server/store.py
    path.write_text(run.model_dump_json(indent=2, exclude={"result": {"brief": {"domain"}}}) + "\n", encoding="utf-8")


def run_case(
    case: Case,
    config_name: str,
    config: ModelConfig,
    repeat: int,
    make_llm: LLMFactory = OpenAILLM,
    snapshots: Path = SNAPSHOTS_DIR,
) -> CaseRun:
    snapshot = load(case, snapshots)
    settings = replace(Settings.from_env(), models=config)
    search = SnapshotSearch(snapshot)
    ctx = RunContext(settings=settings, llm=make_llm(settings), search_client=search)
    result = run_sdr(case.brief, ctx)
    if search.missing:  # the runner records a miss as a failed run; it is a stale snapshot instead
        raise SnapshotMissing(f"{case.id}: snapshot has no search for {search.missing[0]!r}; re-record it")
    return CaseRun(
        case_id=case.id,
        config=config_name,
        models=describe(config),
        repeat=repeat,
        snapshot_recorded_at=snapshot.recorded_at,
        checks=check(case, result),
        result=result,
    )


def usd(value: float | None) -> str:
    return "-" if value is None else f"${value:.4f}"


def summary_line(run: CaseRun) -> str:
    usage = summarize_usage(run.result.llm_calls, run.result.search_calls, run.result.duration_ms)
    verdict = "ok " if run.checks.outcome_ok else "BAD"
    draft = {None: "", True: " draft ok", False: " draft has issues"}[run.checks.draft_ok]
    return (
        f"{verdict} {run.case_id}.{run.repeat}: {run.checks.label} ({run.result.status}),"
        f" model {usd(usage.model_usd)}, {run.result.duration_ms / 1000:.0f} s{draft}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run evaluation cases (paid OpenAI calls).")
    parser.add_argument("--config", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    parser.add_argument("--cases", help="comma-separated case ids; overrides --split")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case")
    parser.add_argument("--name", help="results folder; defaults to the config name")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():  # piped output on Windows defaults to a legacy code page
            stream.reconfigure(encoding="utf-8")

    cases = select(load_cases(), args.split, args.cases.split(",") if args.cases else None)
    for case in cases:
        load(case)  # fail before any paid call if a snapshot is missing or stale
    directory = RESULTS_DIR / (args.name or args.config)
    directory.mkdir(parents=True, exist_ok=True)
    jobs = [
        (case, repeat)
        for case in cases
        for repeat in range(1, args.repeat + 1)
        if not result_path(directory, case.id, repeat).exists()
    ]
    config = CONFIGS[args.config]
    print(f"{len(jobs)} runs with {describe(config)} -> {directory}", file=sys.stderr)

    load_dotenv()

    def work(job: tuple[Case, int]) -> CaseRun:
        case, repeat = job
        run = run_case(case, args.config, config, repeat)
        save_run(run, result_path(directory, case.id, repeat))
        print(summary_line(run), file=sys.stderr, flush=True)
        return run

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        runs = list(pool.map(work, jobs))
    correct = sum(run.checks.outcome_ok for run in runs)
    print(f"Done: {correct}/{len(runs)} outcomes as expected. Report: python -m evals.report", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
