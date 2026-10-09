"""Automatic checks of one run. They are cheap and objective but shallow: a passing run
still needs a human or a separate grader to judge facts, relevance and naturalness."""

import re

from pydantic import BaseModel

from core.schemas import Brief, Fact, Language, RunResult
from evals.cases import Case, Label, outcome_label

PLACEHOLDER = re.compile(r"\[[^\]]{1,40}\]|\{\{[^}]*\}\}|<[A-Z][A-Za-z ]{1,30}>", re.I)
# 40,000 / 40 000 / 1.5 / 30%: thousands groups joined, compared as digits only. Digits inside
# words (B2B, WCAG2) are not numbers; single digits ("1-2 examples") are too common to flag.
NUMBER = re.compile(r"(?<!\w)\d+(?:[,\u00a0\u202f ]\d{3})*(?:\.\d+)?(?!\w)")
CYRILLIC = re.compile(r"[а-яё]", re.I)
LATIN = re.compile(r"[a-z]", re.I)
# Style tics seen in graded drafts (stage 5); reported apart from draft_ok, which they do not change.
STOCK_PHRASES = re.compile(
    r"\b(?:my guess is|i['’]?m guessing|i['’]?m assuming|i assume|i wonder(?:ed)?"
    r"|мо[её] предположение|я предполагаю|предполагаю,)",
    re.I,
)
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+&']*")
RU_PREPOSITIONS = "у|в|во|для|от|о|об|с|со|к|ко|по|из|при|на|про|без|до|после|около"
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
    stock_phrases: list[str] = []  # stock hedges such as "my guess is"
    foreign_words: list[str] = []  # Russian drafts: Latin words that are not names from the brief or facts
    undeclined_company: list[str] = []  # Russian drafts: "у Контур" instead of "у Контура"

    @property
    def draft_ok(self) -> bool | None:
        if not self.has_draft:
            return None
        return bool(self.language_ok and self.length_ok and not self.placeholders and not self.ungrounded_numbers)


def numbers(text: str) -> set[str]:
    found = {re.sub(r"[,\u00a0\u202f ]", "", match) for match in NUMBER.findall(text)}
    return {number for number in found if len(number) > 1}


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


def foreign_words(text: str, facts: list[Fact], brief: Brief) -> list[str]:
    """Latin words in a Russian draft, except names: anything from the brief, and capitalized words
    (brands, products, abbreviations) that the facts also use. "roadmaps", "CTA" and the "support"
    of "support-команда" are flagged unless a fact uses them as written."""
    allowed = {w.lower() for w in LATIN_WORD.findall(f"{brief.company} {brief.website} {brief.offer} {brief.recipient}")}
    in_facts = set(LATIN_WORD.findall(" ".join(f"{fact.claim} {fact.excerpt}" for fact in facts)))
    return [
        word
        for word in LATIN_WORD.findall(text)
        if word.lower() not in allowed and not (word[0].isupper() and word in in_facts)
    ]


def undeclined_company(text: str, company: str) -> list[str]:
    """A Cyrillic company name left in the nominative after a preposition: "у Контур", "в Контур".
    Names ending in о, е, и, у, ю do not decline in Russian and are not checked; neither are
    Latin names or names in quotes («Контур»), which stay unchanged with a generic word."""
    if not CYRILLIC.search(company) or LATIN.search(company) or company[-1].lower() in "оеиую":
        return []
    pattern = re.compile(rf"\b(?:{RU_PREPOSITIONS})\s+{re.escape(company)}(?![а-яё])", re.I)
    return pattern.findall(text)


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
            "stock_phrases": STOCK_PHRASES.findall(text),
            "foreign_words": foreign_words(text, research.facts if research else [], case.brief)
            if language == "Russian"
            else [],
            "undeclined_company": undeclined_company(text, case.brief.company) if language == "Russian" else [],
        }
    )
