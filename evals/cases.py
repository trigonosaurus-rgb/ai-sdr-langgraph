"""Evaluation cases from cases.toml and the outcome label a run is judged by."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.schemas import Brief, RunResult

EVALS_DIR = Path(__file__).resolve().parent
CASES_FILE = EVALS_DIR / "cases.toml"

Expected = Literal["draft", "poor_fit", "insufficient_data", "website_mismatch"]
Label = Expected | Literal["error"]
Split = Literal["dev", "holdout", "all"]


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    brief: Brief
    expect: list[Expected] = Field(min_length=1)  # any of these outcomes is correct
    holdout: bool = False
    note: str = ""


def parse_cases(text: str) -> list[Case]:
    cases = []
    for entry in tomllib.loads(text)["case"]:
        meta = {key: entry.pop(key) for key in ("id", "expect", "holdout", "note") if key in entry}
        cases.append(Case(brief=Brief(**entry), **meta))
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case ids must be unique")
    return cases


def load_cases(path: Path = CASES_FILE) -> list[Case]:
    return parse_cases(path.read_text(encoding="utf-8"))


def select(cases: list[Case], split: Split = "dev", ids: list[str] | None = None) -> list[Case]:
    """Cases of a split, or exactly the named ones in the given order."""
    if ids:
        by_id = {case.id: case for case in cases}
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise ValueError(f"unknown cases: {', '.join(unknown)}")
        return [by_id[i] for i in ids]
    if split == "all":
        return cases
    return [case for case in cases if case.holdout == (split == "holdout")]


def outcome_label(result: RunResult) -> Label:
    if result.status == "failed":
        if result.reason in ("insufficient_data", "website_mismatch"):
            return result.reason
        return "error"
    if result.strategy and result.strategy.offer_fit == "poor":
        return "poor_fit"
    return "draft"
