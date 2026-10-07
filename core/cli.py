"""Manual run from the terminal. Makes PAID OpenAI and Tavily calls.

python -m core.cli --company Acme --website acme.com --offer "..." --recipient "Head of Sales"
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from core.config import Settings
from core.context import RunContext
from core.llm import OpenAILLM
from core.runner import run_sdr
from core.schemas import Brief
from core.search import TavilySearch

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def print_event(event: dict) -> None:
    kind = event["type"]
    if kind in ("stage", "activity"):
        prefix = f"[{event['stage']}]" if kind == "stage" else "   "
        line = f"{prefix} {event['message']}"
    elif kind == "evidence":
        line = "   facts:\n" + "\n".join(f"     {s['id']}. {s['claim']} ({s['path']})" for s in event["sources"])
    elif kind == "strategy":
        line = f"   angle: {event['strategy']['angle']} (fit: {event['strategy']['offerFit']})"
    elif kind == "review":
        verdict = "passed" if event["passed"] else "rejected"
        line = f"   draft {event['attempt']} {verdict}" + "".join(f"\n     - {i}" for i in event["issues"])
    elif kind in ("completed", "failed"):
        line = f"== {kind}: {event.get('outcome') or event.get('reason')}"
    else:
        return
    print(line, file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Research a company and draft a cold email (paid API calls).")
    parser.add_argument("--company", required=True)
    parser.add_argument("--website", required=True)
    parser.add_argument("--offer", required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--language", default="English", choices=["English", "Russian"])
    parser.add_argument("--tone", default="Direct", choices=["Direct", "Warm"])
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():  # piped output on Windows defaults to a legacy code page
            stream.reconfigure(encoding="utf-8")

    try:
        brief = Brief(**vars(args))
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 2

    load_dotenv()
    settings = Settings.from_env()
    ctx = RunContext(settings=settings, llm=OpenAILLM(settings), search_client=TavilySearch())
    result = run_sdr(brief, ctx, on_event=print_event)

    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{result.run_id}.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    print(f"\n{result.status}: {result.message}", file=sys.stderr)
    if result.draft:
        print(f"\nSubject: {result.draft.subject}\n\n{result.draft.body}\n")
    print(f"Full result: {path}", file=sys.stderr)
    return 0 if result.status == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
