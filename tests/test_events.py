"""Event stream format and its match with the frontend contract in frontend/src/run.ts."""

import re
from pathlib import Path

from typing import get_args

from core.events import Payload
from core.runner import run_sdr
from core.schemas import FailureReason, Usage
from fakes import PASS, FakeLLM, draft, happy_script, reject

RUN_TS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "run.ts"


def collect(brief, ctx):
    events: list[dict] = []
    run_sdr(brief, ctx, run_id="run-1", on_event=events.append)
    return events


def test_events_are_numbered_and_stamped(brief, make_ctx):
    events = collect(brief, make_ctx(FakeLLM(happy_script())))

    assert [e["sequence"] for e in events] == list(range(len(events)))
    assert {e["runId"] for e in events} == {"run-1"}
    stages = [e for e in events if e["type"] == "stage"]
    assert [e["stage"] for e in stages] == ["Research", "Strategy", "Writing", "Review"]
    elapsed = [e["elapsedMs"] for e in stages] + [events[-1]["elapsedMs"]]
    assert elapsed == sorted(elapsed) and elapsed[0] > 0


def collapsed_types(events):
    """Event types with each run of draft_delta folded into one: the count depends on chunking."""
    result = []
    for event in events:
        if not (event["type"] == "draft_delta" and result and result[-1] == "draft_delta"):
            result.append(event["type"])
    return result


def drafted(events) -> dict[str, str]:
    """The draft a client shows: deltas concatenated since the last draft_reset."""
    draft = {"subject": "", "body": ""}
    for event in events:
        if event["type"] == "draft_reset":
            draft = {"subject": "", "body": ""}
        elif event["type"] == "draft_delta":
            draft[event["field"]] += event["delta"]
    return draft


def test_order_of_a_ready_run(brief, make_ctx):
    events = collect(brief, make_ctx(FakeLLM(happy_script())))
    assert collapsed_types(events) == [
        "started",
        "stage",
        "activity",
        "activity",
        "evidence",
        "stage",
        "strategy",
        "stage",
        "draft_reset",
        "draft_delta",
        "stage",
        "review",
        "completed",
    ]


def test_draft_is_streamed_in_many_deltas_that_add_up_to_the_draft(brief, make_ctx):
    events = collect(brief, make_ctx(FakeLLM(happy_script())))
    deltas = [e for e in events if e["type"] == "draft_delta"]
    assert len(deltas) > 4
    assert drafted(events) == draft(1).model_dump()


def test_streamed_draft_matches_the_stripped_final_draft(brief, make_ctx):
    from core.schemas import Draft

    padded = Draft(subject="  Warsaw team ", body="\n Hello there.\n\nSecond line. \n")
    events = collect(brief, make_ctx(FakeLLM(happy_script(Writing=[padded]), chunk_chars=1)))
    assert drafted(events) == {"subject": "Warsaw team", "body": "Hello there.\n\nSecond line."}
    assert not any(e["delta"] == "" for e in events if e["type"] == "draft_delta")


def test_rewrite_resets_and_streams_the_new_draft(brief, make_ctx):
    llm = FakeLLM(happy_script(Writing=[draft(1), draft(2)], Review=[reject("x"), PASS]))
    events = collect(brief, make_ctx(llm))
    resets = [e["attempt"] for e in events if e["type"] == "draft_reset"]
    assert resets == [1, 2]
    assert drafted(events) == draft(2).model_dump()


def test_draft_stream_repairs_a_partial_that_was_not_a_prefix():
    from agents.copywriter import DraftStream
    from core.schemas import Draft

    sent: list = []
    import agents.copywriter as copywriter

    original, copywriter.emit = copywriter.emit, sent.append
    try:
        stream = DraftStream(attempt=1)
        stream.update({"subject": "Hello wor"})
        stream.update({"subject": "Hello"})  # shorter: ignored, nothing is taken back
        stream.finish(Draft(subject="Help wanted", body="Body."))
    finally:
        copywriter.emit = original
    events = [e.model_dump(by_alias=True) for e in sent]
    assert [e["type"] for e in events] == ["draft_delta", "draft_reset", "draft_delta", "draft_delta"]
    assert drafted(events) == {"subject": "Help wanted", "body": "Body."}


def test_wire_format_is_camel_case(brief, make_ctx):
    events = collect(brief, make_ctx(FakeLLM(happy_script())))
    by_type = {e["type"]: e for e in events}

    assert by_type["evidence"]["sources"][0] == {
        "id": 1,
        "claim": "Acme sells route planning software to delivery fleets.",
        "title": "About Acme",
        "url": "https://acme.com/about",
        "path": "acme.com/about",
        "excerpt": "Acme builds route planning software for regional delivery fleets",
    }
    assert set(by_type["strategy"]["strategy"]) == {
        "observation",
        "factIds",
        "offerLink",
        "hypotheses",
        "angle",
        "offerFit",
        "fitReason",
    }
    assert set(by_type["draft_delta"]) == {"type", "field", "delta", "runId", "sequence"}
    assert by_type["completed"]["usage"] == {
        "input": 400,
        "cachedInput": 80,
        "output": 200,
        "reasoning": 40,
        "modelUsd": None,
        "searchUsd": 0.024,  # three searches, one credit each
        "durationSeconds": by_type["completed"]["elapsedMs"] / 1000,
        "model": "fake-model",
    }


def test_unknown_usage_is_null_not_zero(brief, make_ctx):
    events = collect(brief, make_ctx(FakeLLM(happy_script(), usage=Usage())))
    usage = events[-1]["usage"]
    assert usage["input"] is None and usage["output"] is None and usage["reasoning"] is None


def test_review_events_follow_attempts(brief, make_ctx):
    llm = FakeLLM(happy_script(Writing=[draft(1), draft(2)], Review=[reject("x"), PASS]))
    events = collect(brief, make_ctx(llm))
    reviews = [(e["attempt"], e["passed"], e["issues"]) for e in events if e["type"] == "review"]
    assert reviews == [(1, False, ["x"]), (2, True, [])]


def test_python_events_match_frontend_contract():
    """Every event type the server emits is declared in run.ts, and vice versa."""
    source = RUN_TS.read_text(encoding="utf-8")
    union = source.split("type Payload =", 1)[1].split("export type RunEvent", 1)[0]
    ts_types = set(re.findall(r"type: '(\w+)'", union))
    py_types = {cls.model_fields["type"].default for cls in _payload_classes()}
    assert ts_types == py_types


def test_failure_reasons_match_frontend_contract():
    source = RUN_TS.read_text(encoding="utf-8")
    declaration = source.split("export type FailureReason =", 1)[1].split("export", 1)[0]
    assert set(re.findall(r"'(\w+)'", declaration)) == set(get_args(FailureReason))


def _payload_classes():
    pending, found = list(Payload.__subclasses__()), []
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        if "type" in cls.model_fields:
            found.append(cls)
    return found
