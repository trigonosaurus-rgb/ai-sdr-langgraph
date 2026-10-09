"""Evaluation harness: cases, snapshots, checks and the report, on fakes without network."""

import pytest

from core.config import Settings, stage_models
from core.llm import LLMError
from core.runner import run_sdr
from core.schemas import Fact
from evals.cases import Case, load_cases, outcome_label, parse_cases, select
from evals.checks import check, language_ok, ungrounded_numbers
from evals.grades import Grade
from evals.report import summarize
from evals.run import run_case
from evals.snapshot import SnapshotMissing, load, record, save
from fakes import FakeLLM, happy_script, research_output, strategy


@pytest.fixture
def case(brief) -> Case:
    return Case(id="acme", brief=brief, expect=["draft"])


def replay(case: Case, snapshots, script: dict, repeat: int = 1):
    config = stage_models("fake-model")
    return run_case(case, "fake", config, repeat, make_llm=lambda _: FakeLLM(script), snapshots=snapshots)


def fact(claim: str, excerpt: str = "") -> Fact:
    return Fact(id=1, claim=claim, excerpt=excerpt, source_url="https://acme.com", source_title="Acme")


def test_case_file_covers_every_expected_outcome_and_keeps_a_holdout():
    cases = load_cases()
    assert 20 <= len(cases) <= 30
    assert {label for case in cases for label in case.expect} == {
        "draft",
        "poor_fit",
        "insufficient_data",
        "website_mismatch",
    }
    assert {case.brief.language for case in cases} == {"English", "Russian"}
    holdout = select(cases, "holdout")
    assert 0 < len(holdout) < len(cases) / 2
    assert len(select(cases, "dev")) + len(holdout) == len(cases)


def test_cases_parse_brief_fields_and_reject_duplicates():
    text = """
    [[case]]
    id = "a"
    company = "Acme"
    website = "acme.com"
    offer = "Audits"
    recipient = "CTO"
    expect = ["draft"]
    holdout = true
    """
    (case,) = parse_cases(text)
    assert case.holdout and case.brief.language == "English" and case.brief.domain == "acme.com"
    with pytest.raises(ValueError, match="unique"):
        parse_cases(text + text)


def test_select_by_ids_keeps_their_order():
    cases = load_cases()
    assert [c.id for c in select(cases, ids=["stripe", "linear"])] == ["stripe", "linear"]
    with pytest.raises(ValueError, match="nope"):
        select(cases, ids=["nope"])


@pytest.mark.parametrize(
    ("script", "label"),
    [
        (happy_script(), "draft"),
        (happy_script(Strategy=[strategy(offer_fit="poor")]), "poor_fit"),
        (happy_script(Research=[research_output(sufficient=False)]), "insufficient_data"),
        (happy_script(Research=[research_output(website_matches=False)]), "website_mismatch"),
        (happy_script(Research=[LLMError("boom")]), "error"),
    ],
)
def test_outcome_label(brief, make_ctx, script, label):
    assert outcome_label(run_sdr(brief, make_ctx(FakeLLM(script)))) == label


def test_language_check_allows_latin_brand_names_in_russian():
    assert language_ok("Привет! Видел, что Linear запустил Customer Requests для команд.", "Russian")
    assert not language_ok("Hi! Saw that Linear launched Customer Requests.", "Russian")
    assert language_ok("Hi! Saw that Linear launched Customer Requests.", "English")
    assert not language_ok("Hi, Контур!", "English")


def test_numbers_must_come_from_facts_or_the_brief(brief):
    facts = [fact("Used by over 40,000 product teams", "more than 40 000 teams")]
    assert ungrounded_numbers("Over 40,000 teams use it", facts, brief) == []
    assert ungrounded_numbers("Over 45,000 teams, 30% faster", facts, brief) == ["30", "45000"]
    assert ungrounded_numbers("B2B teams, 1-2 examples, 480k orders", facts, brief) == []
    with_offer = brief.model_copy(update={"offer": "WCAG 2.2 audits"})
    assert ungrounded_numbers("Audits against WCAG 2.2", [], with_offer) == []


def test_checks_flag_placeholders_length_and_outcome(brief, make_ctx):
    result = run_sdr(brief, make_ctx(FakeLLM(happy_script())))
    result.draft.body = "Hi [Name], " + "word " * 60
    checks = check(Case(id="acme", brief=brief, expect=["insufficient_data"]), result)
    assert checks.label == "draft" and not checks.outcome_ok
    assert checks.placeholders == ["[Name]"] and checks.length_ok and checks.language_ok
    assert checks.facts == 2 and checks.attempts == 1 and checks.draft_ok is False


def test_snapshot_replays_the_same_sources_and_credits(tmp_path, case, search):
    save(record(case, search, Settings()), tmp_path)
    recorded_queries = list(search.queries)

    run = replay(case, tmp_path, happy_script())

    assert search.queries == recorded_queries  # nothing was searched again
    assert run.checks.outcome_ok and run.result.status == "ready"
    assert [call.credits for call in run.result.search_calls] == [1, 1, 1]
    sources = [f.source_url for f in run.result.research.facts]
    assert sources == ["https://acme.com/about", "https://news.example.com/acme-warsaw"]
    assert run.models.startswith("Research fake-model/low")


def test_changed_queries_raise_instead_of_counting_as_a_failed_run(tmp_path, case, search):
    snapshot = record(case, search, Settings())
    save(snapshot.model_copy(update={"searches": snapshot.searches[:2]}), tmp_path)
    with pytest.raises(SnapshotMissing, match="news"):
        replay(case, tmp_path, happy_script())


def test_a_changed_brief_needs_a_new_snapshot(tmp_path, case, search):
    save(record(case, search, Settings()), tmp_path)
    changed = case.model_copy(update={"brief": case.brief.model_copy(update={"offer": "Something else"})})
    with pytest.raises(SnapshotMissing, match="changed"):
        load(changed, tmp_path)
    with pytest.raises(SnapshotMissing, match="no search snapshot"):
        load(case.model_copy(update={"id": "other"}), tmp_path)


def test_report_counts_successes_only_once_every_draft_is_graded(tmp_path, case, search):
    save(record(case, search, Settings()), tmp_path)
    thin = happy_script(Research=[research_output(sufficient=False)])
    runs = [
        replay(case, tmp_path, happy_script(), repeat=1),
        replay(case, tmp_path, happy_script(), repeat=2),
        replay(case, tmp_path, thin, repeat=3),  # refused although a draft was expected
    ]
    lenient = case.model_copy(update={"id": "thin", "expect": ["draft", "insufficient_data"]})
    save(record(lenient, search, Settings()), tmp_path)
    runs.append(replay(lenient, tmp_path, thin))  # an accepted refusal succeeds without a grade

    ungraded = summarize("fake", runs, expected_draft={"acme"})
    assert (ungraded.runs, ungraded.outcome_ok, ungraded.ready, ungraded.drafts_expected) == (4, 3, 2, 3)
    assert ungraded.successes is None and ungraded.grounding is None

    grades = {
        "acme.1": Grade(grounding=2, relevance=2, naturalness=1),
        "acme.2": Grade(grounding=1, relevance=2, naturalness=2),
    }
    row = summarize("fake", runs, expected_draft={"acme"}, grades=grades)
    assert row.successes == 2 and row.graded == 2  # the second draft is not fully grounded
    assert row.grounding == 1.5 and row.naturalness == 1.5
    assert row.model_usd is None and row.usd_per_success is None  # fake-model has no price: unknown, never zero

