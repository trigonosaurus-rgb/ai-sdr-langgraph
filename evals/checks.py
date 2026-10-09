"""Automatic checks of one run. They are cheap and objective but shallow: a passing run
still needs a human or a separate grader to judge facts, relevance and naturalness."""

import re

from pydantic import BaseModel

from core.schemas import Brief, Fact, Language, RunResult
from evals.cases import Case, Label, outcome_label

PLACEHOLDER = re.compile(r"\[[^\]]{1,40}\]|\{\{[^}]*\}\}|<[A-Z][A-Za-z ]{1,30}>", re.I)
# 40,000 / 40 000 / 1.5 / 30%: thousands groups joined, the result compared as digits only
NUMBER = re.compile(r"\d+(?:[,\u00a0\u202f ]\d{3})*(?:\.\d+)?")
CYRILLIC = re.compile(r"[а-яё]", re.I)
LATIN = re.compile(r"[a-z]", re.I)
BODY_WORDS = (50, 120)
SUBJECT_MAX_WORDS = 7  # the prompts ask for under 8


class Checks(BaseModel):
    label: Label
    outcome_ok: bool
    facts: int | None  # verified facts; None when research did not finish
    dropped_facts: int | None
    attempts: int
    has_draft: bool
    language_ok: bool | None = None  # None: no draft to check
    body_words: int | None = None
    subject_words: int | None = None
    length_ok: bool | None = None
    placeholders: list[str] = []
    ungrounded_numbers: list[str] = []  # numbers in the draft found neither in the facts nor in the brief

    @property
    def draft_ok(self) -> bool | None:
        if not self.has_draft:
            return None
        return bool(self.language_ok and self.length_ok and not self.placeholders and not self.ungrounded_numbers)


def numbers(text: str) -> set[str]:
    return {re.sub(r"[,\u00a0\u202f ]", "", match) for match in NUMBER.findall(text)}


def language_ok(text: str, language: Language) -> bool:
    cyrillic, latin = len(CYRILLIC.findall(text)), len(LATIN.findall(text))
    if language == "Russian":  # brand and product names stay in Latin script
        return cyrillic > 0.5 * (cyrillic + latin)
    return cyrillic == 0


def ungrounded_numbers(text: str, facts: list[Fact], brief: Brief) -> list[str]:
    known = numbers(f"{brief.company} {brief.offer} {brief.recipient}")
    for fact in facts:
        known |= numbers(f"{fact.claim} {fact.excerpt}")
    return sorted(numbers(text) - known)


def check(case: Case, result: RunResult) -> Checks:
    label = outcome_label(result)
    research = result.research
    checks = Checks(
        label=label,
        outcome_ok=label in case.expect,
        facts=len(research.facts) if research else None,
        dropped_facts=research.dropped_facts if research else None,
        attempts=len(result.attempts),
        has_draft=result.draft is not None,
    )
    if result.draft is None:
        return checks
    draft, language = result.draft, case.brief.language
    body_words, subject_words = len(draft.body.split()), len(draft.subject.split())
    text = f"{draft.subject}\n{draft.body}"
    return checks.model_copy(
        update={
            "language_ok": language_ok(text, language),
            "body_words": body_words,
            "subject_words": subject_words,
            "length_ok": BODY_WORDS[0] <= body_words <= BODY_WORDS[1] and subject_words <= SUBJECT_MAX_WORDS,
            "placeholders": PLACEHOLDER.findall(text),
            "ungrounded_numbers": ungrounded_numbers(text, research.facts if research else [], case.brief),
        }
    )
