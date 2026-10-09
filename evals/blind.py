"""Blind grading by a human: a shuffled sample of drafts with the configuration hidden.

python -m evals.blind sample mini-v1 mini-v2 luna-v2 sol-v2 --cases 7 --seed 5
    writes blind/sample.json (what the grader sees) and blind/key.json (item -> results folder, run)
python -m evals.blind import grades.json
    splits {item: {grounding, relevance, naturalness, note}} into grades/<results>.human.json
    and prints the agreement with Claude's grades on the same drafts
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from evals.cases import EVALS_DIR, load_cases
from evals.grades import GRADES_DIR, Grade, GradeFile, grades_path, load_grades
from evals.run import RESULTS_DIR, CaseRun

BLIND_DIR = EVALS_DIR / "blind"
CRITERIA = ("grounding", "relevance", "naturalness")


class Item(BaseModel):
    """One draft as the grader sees it: nothing names the model or the prompt version."""

    id: str
    company: str
    website: str
    recipient: str
    offer: str
    language: str
    tone: str
    facts: list[dict[str, str]]  # claim, excerpt, url
    subject: str
    body: str


def build_sample(results: list[str], cases: int, seed: int) -> tuple[list[Item], dict[str, str]]:
    """The first repeat of `cases` dev cases that expect a draft, from every results folder."""
    rng = random.Random(seed)
    candidates = [c for c in load_cases() if not c.holdout and c.expect == ["draft"]]
    russian = [c for c in candidates if c.brief.language == "Russian"]
    picked = rng.sample(russian, min(2, len(russian)))
    picked += rng.sample([c for c in candidates if c not in picked], cases - len(picked))

    items, key = [], {}
    for name in results:
        for case in picked:
            path = RESULTS_DIR / name / f"{case.id}.1.json"
            if not path.exists():
                continue
            run = CaseRun.model_validate_json(path.read_text(encoding="utf-8"))
            result = run.result
            if result.draft is None or result.research is None:
                continue  # a refusal is judged by the outcome check, not graded
            facts = [{"claim": f.claim, "excerpt": f.excerpt, "url": f.source_url} for f in result.research.facts]
            items.append(
                Item(
                    id="",
                    company=case.brief.company,
                    website=case.brief.domain,
                    recipient=case.brief.recipient,
                    offer=case.brief.offer,
                    language=case.brief.language,
                    tone=case.brief.tone,
                    facts=facts,
                    subject=result.draft.subject,
                    body=result.draft.body,
                )
            )
            key[str(len(items) - 1)] = f"{name}/{case.id}.1"
    order = list(range(len(items)))
    rng.shuffle(order)
    shuffled, blind_key = [], {}
    for number, index in enumerate(order, start=1):
        item_id = f"d{number:02d}"
        shuffled.append(items[index].model_copy(update={"id": item_id}))
        blind_key[item_id] = key[str(index)]
    return shuffled, blind_key


def import_grades(raw: dict[str, dict], key: dict[str, str], directory: Path = GRADES_DIR) -> dict[str, dict[str, Grade]]:
    by_results: dict[str, dict[str, Grade]] = defaultdict(dict)
    for item_id, values in raw.items():
        name, run = key[item_id].split("/")
        by_results[name][run] = Grade(**{k: values[k] for k in (*CRITERIA, "note") if k in values})
    for name, grades in by_results.items():
        file = GradeFile(
            grader="human",
            graded_at=datetime.now(UTC).date().isoformat(),
            scale="evals/README.md: grounding, relevance, naturalness, 0-2 each",
            scope="blind sample from evals/blind/sample.json; configuration hidden",
            grades=grades,
        )
        grades_path(name, "human", directory).write_text(file.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return by_results


def agreement(human: dict[str, dict[str, Grade]], directory: Path = GRADES_DIR) -> str:
    exact, near, total = 0, 0, 0
    lines = []
    for criterion in CRITERIA:
        diffs = []
        for name, grades in human.items():
            claude = load_grades(name, "claude", directory) or {}
            for run, grade in grades.items():
                if run in claude:
                    diffs.append(getattr(claude[run], criterion) - getattr(grade, criterion))
        if diffs:
            exact += sum(d == 0 for d in diffs)
            near += sum(abs(d) <= 1 for d in diffs)
            total += len(diffs)
            bias = sum(diffs) / len(diffs)
            lines.append(f"- {criterion}: exact {sum(d == 0 for d in diffs)}/{len(diffs)}, Claude minus human {bias:+.2f}")
    if not total:
        return "No overlapping grades."
    return f"Exact agreement {exact}/{total}, within one point {near}/{total}\n" + "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Blind human grading of drafts.")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample")
    sample.add_argument("results", nargs="+")
    sample.add_argument("--cases", type=int, default=7)
    sample.add_argument("--seed", type=int, default=5)
    imported = commands.add_parser("import")
    imported.add_argument("file", type=Path)
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")

    BLIND_DIR.mkdir(exist_ok=True)
    if args.command == "sample":
        items, key = build_sample(args.results, args.cases, args.seed)
        (BLIND_DIR / "sample.json").write_text(
            json.dumps([i.model_dump() for i in items], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (BLIND_DIR / "key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"{len(items)} drafts from {len(args.results)} folders -> {BLIND_DIR}", file=sys.stderr)
    else:
        key = json.loads((BLIND_DIR / "key.json").read_text(encoding="utf-8"))
        raw = json.loads(args.file.read_text(encoding="utf-8"))
        print(agreement(import_grades(raw, key)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
