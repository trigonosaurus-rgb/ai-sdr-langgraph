"""End-to-end runs of the graph on fakes: outcomes, rewrites, refusals and failures."""

import threading

from core.llm import LLMError
from core.runner import run_sdr
from core.schemas import Brief, ExtractedFact
from core.search import SearchError
from fakes import (
    PASS,
    FakeLLM,
    FakeSearch,
    draft,
    happy_script,
    reject,
    research_output,
    strategy,
)


def run(brief, ctx):
    events: list[dict] = []
    result = run_sdr(brief, ctx, run_id="run-1", on_event=events.append)
    return result, events


def types(events):
    return [event["type"] for event in events]


def test_ready_run_has_sourced_facts_strategy_and_reviewed_draft(brief, make_ctx):
    llm = FakeLLM(happy_script())
    result, events = run(brief, make_ctx(llm))

    assert result.status == "ready" and result.reason is None
    assert result.draft == draft(1)
    assert [f.source_url for f in result.research.facts] == [
        "https://acme.com/about",
        "https://news.example.com/acme-warsaw",
    ]
    assert result.strategy.fact_ids == [2]  # unknown fact id 99 removed
    assert result.prompt_versions == {
        "research": "research@1",
        "strategy": "strategy@1",
        "copywriter": "copywriter@1",
        "review": "review@1",
    }
    assert [c.prompt_version for c in result.llm_calls] == [
        "research@1",
        "strategy@1",
        "copywriter@1",
        "review@1",
    ]
    assert len(result.search_calls) == 3
    assert types(events)[0] == "started" and types(events)[-1] == "completed"
    assert events[-1]["outcome"] == "ready"


def test_search_covers_official_site_open_web_and_news(brief, make_ctx, search):
    run(brief, make_ctx(FakeLLM(happy_script())))
    assert [(topic, domains) for _, topic, domains in search.queries] == [
        ("general", ["acme.com"]),
        ("general", None),
        ("news", None),
    ]


def test_brief_reaches_prompts(make_ctx):
    brief = Brief(
        company="Acme",
        website="acme.com",
        offer="Contract data engineers",
        recipient="CTO",
        language="Russian",
        tone="Warm",
    )
    llm = FakeLLM(happy_script())
    run(brief, make_ctx(llm))
    strategy_call, writing_call, review_call = llm.calls[1:]
    assert "Contract data engineers" in strategy_call.user and "CTO" in strategy_call.user
    assert "Russian" in writing_call.system and "warm and personable" in writing_call.system
    assert "Russian" in review_call.system


def test_llm_error_fails_the_run_instead_of_becoming_the_draft(brief, make_ctx):
    llm = FakeLLM(happy_script(Writing=[LLMError("rate limited")]))
    result, events = run(brief, make_ctx(llm))

    assert result.status == "failed" and result.reason == "error"
    assert result.draft is None
    assert "rate limited" in result.message
    assert "completed" not in types(events)
    failed = events[-1]
    assert failed["type"] == "failed" and failed["stage"] == "Writing"
    assert "rate limited" not in failed["message"]  # provider details stay server-side
    assert result.llm_calls[-1].error == "rate limited"


def test_review_error_is_not_a_pass(brief, make_ctx):
    llm = FakeLLM(happy_script(Review=[LLMError("No valid Review: bad json")]))
    result, events = run(brief, make_ctx(llm))
    assert result.status == "failed" and events[-1]["stage"] == "Review"
    assert "review" not in types(events)


def test_rejected_without_reasons_still_counts_as_rejected(brief, make_ctx):
    from core.schemas import Review

    silent = Review(passed=False, issues=[])
    llm = FakeLLM(happy_script(Writing=[draft(1)], Review=[silent]))
    result, _ = run(brief, make_ctx(llm, max_rewrites=0))
    assert result.status == "needs_attention"
    assert result.issues == ["The reviewer rejected the draft without naming a problem."]


def test_rewrite_sees_previous_draft_and_issues_then_passes(brief, make_ctx):
    llm = FakeLLM(
        happy_script(Writing=[draft(1), draft(2)], Review=[reject("Cut the buzzword 'synergy'."), PASS])
    )
    result, events = run(brief, make_ctx(llm))

    assert result.status == "ready" and result.draft == draft(2)
    rewrite = [c for c in llm.calls if c.stage == "Writing"][1]
    assert "Body of draft 1." in rewrite.user and "Cut the buzzword 'synergy'." in rewrite.user
    first = [c for c in llm.calls if c.stage == "Writing"][0]
    assert "Previous draft" not in first.user
    assert [e["attempt"] for e in events if e["type"] == "draft_reset"] == [1, 2]


def test_rewrite_limit_gives_needs_attention_with_last_draft(brief, make_ctx):
    llm = FakeLLM(
        happy_script(
            Writing=[draft(1), draft(2), draft(3)],
            Review=[reject("a"), reject("b"), reject("c")],
        )
    )
    result, events = run(brief, make_ctx(llm, max_rewrites=2))

    assert llm.stages().count("Writing") == 3
    assert result.status == "needs_attention"
    assert result.draft == draft(3) and result.issues == ["c"]
    assert [a.attempt for a in result.attempts] == [1, 2, 3]
    assert events[-1] == {**events[-1], "type": "completed", "outcome": "needs_attention", "issues": ["c"]}


def test_rewrite_limit_comes_from_settings(brief, make_ctx):
    llm = FakeLLM(happy_script(Writing=[draft(1)], Review=[reject()]))
    result, _ = run(brief, make_ctx(llm, max_rewrites=0))
    assert result.status == "needs_attention" and len(result.attempts) == 1


def test_insufficient_data_stops_before_strategy(brief, make_ctx):
    llm = FakeLLM(
        happy_script(Research=[research_output(sufficient=False, gaps="What Acme sells")])
    )
    result, events = run(brief, make_ctx(llm))

    assert llm.stages() == ["Research"]
    assert result.status == "failed" and result.reason == "insufficient_data"
    assert "What Acme sells" in result.message
    assert result.draft is None and result.strategy is None
    assert events[-1]["type"] == "failed" and events[-1]["reason"] == "insufficient_data"


def test_too_few_verified_facts_is_insufficient(brief, make_ctx):
    invented = ExtractedFact(
        claim="Acme raised $50M.", source_id=1, excerpt="Acme raised a $50M Series C"
    )
    wrong_source = ExtractedFact(claim="x", source_id=7, excerpt="route planning software")
    good = research_output().facts[0]
    llm = FakeLLM(happy_script(Research=[research_output(facts=[invented, wrong_source, good])]))
    result, _ = run(brief, make_ctx(llm))

    assert result.reason == "insufficient_data"
    assert [f.claim for f in result.research.facts] == [good.claim]
    assert result.research.dropped_facts == 2 == len(result.research.dropped)


def test_no_search_results_skips_the_llm(brief, make_ctx):
    llm = FakeLLM({})
    result, _ = run(brief, make_ctx(llm, search_client=FakeSearch()))
    assert llm.calls == []
    assert result.reason == "insufficient_data"


def test_wrong_website_is_reported(brief, make_ctx):
    llm = FakeLLM(
        happy_script(
            Research=[
                research_output(
                    website_matches=False,
                    website_note="acme.com belongs to a hardware store, not the software company.",
                )
            ]
        )
    )
    result, events = run(brief, make_ctx(llm))
    assert result.reason == "website_mismatch"
    assert "hardware store" in result.message and "acme.com" in result.message
    assert llm.stages() == ["Research"]


def test_search_failure_fails_the_run(brief, make_ctx):
    search = FakeSearch(error=SearchError("Tavily 432: plan limit"))
    result, events = run(brief, make_ctx(FakeLLM({}), search_client=search))
    assert result.status == "failed" and events[-1]["stage"] == "Research"
    assert result.search_calls[0].error == "Tavily 432: plan limit"


def test_poor_offer_fit_needs_attention_but_keeps_the_draft(brief, make_ctx):
    llm = FakeLLM(
        happy_script(Strategy=[strategy(offer_fit="poor", fit_reason="Acme has two employees.")])
    )
    result, _ = run(brief, make_ctx(llm))
    assert result.status == "needs_attention" and result.draft == draft(1)
    assert result.issues == ["The offer may not fit this company: Acme has two employees."]


def test_empty_draft_fails(brief, make_ctx):
    from core.schemas import Draft

    llm = FakeLLM(happy_script(Writing=[Draft(subject=" ", body="text")]))
    result, _ = run(brief, make_ctx(llm))
    assert result.status == "failed" and result.reason == "error"



class CancellingLLM(FakeLLM):
    """Sets the cancel flag right after answering the given stage, as a user clicking Cancel would."""

    def __init__(self, script, after_stage: str):
        super().__init__(script)
        self.after_stage = after_stage
        self.cancel = threading.Event()

    def generate(self, stage, schema, system, user, on_partial=None):
        reply = super().generate(stage, schema, system, user, on_partial)
        if stage == self.after_stage:
            self.cancel.set()
        return reply


def run_cancelling(brief, make_ctx, after_stage: str):
    llm = CancellingLLM(happy_script(), after_stage)
    ctx = make_ctx(llm)
    ctx.cancel = llm.cancel
    return run(brief, ctx)


def test_cancel_stops_before_the_next_paid_call(brief, make_ctx):
    result, events = run_cancelling(brief, make_ctx, after_stage="Research")
    assert result.status == "failed" and result.reason == "cancelled"
    assert [c.stage for c in result.llm_calls] == ["Research"]
    assert result.draft is None
    assert events[-1]["type"] == "failed" and events[-1]["reason"] == "cancelled"
    assert events[-1]["stage"] == "Strategy"


def test_cancel_after_the_last_paid_call_keeps_the_result(brief, make_ctx):
    result, _ = run_cancelling(brief, make_ctx, after_stage="Review")
    assert result.status == "ready"
