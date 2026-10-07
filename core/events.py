"""Run events, mirroring the RunEvent union in frontend/src/run.ts.

Nodes emit payloads through LangGraph's custom stream; the runner adds runId,
sequence and server-measured elapsedMs before handing events to consumers.
"""

from typing import Literal

from langgraph.config import get_stream_writer
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from core.schemas import FailureReason, Stage


class Payload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Started(Payload):
    type: Literal["started"] = "started"
    company: str
    recipient: str


class StageStarted(Payload):
    type: Literal["stage"] = "stage"
    stage: Stage
    message: str
    elapsed_ms: int | None = None


class Activity(Payload):
    """Progress note inside the current stage; does not restart its timer."""

    type: Literal["activity"] = "activity"
    message: str


class EvidenceItem(Payload):
    id: int
    claim: str
    title: str
    url: str
    path: str  # short display form of url
    excerpt: str


class Evidence(Payload):
    type: Literal["evidence"] = "evidence"
    sources: list[EvidenceItem]


class StrategyView(Payload):
    observation: str
    fact_ids: list[int]
    offer_link: str
    hypotheses: list[str]
    angle: str
    offer_fit: Literal["good", "weak", "poor"]
    fit_reason: str


class StrategyReady(Payload):
    type: Literal["strategy"] = "strategy"
    strategy: StrategyView


class DraftReset(Payload):
    type: Literal["draft_reset"] = "draft_reset"
    attempt: int


class DraftDelta(Payload):
    type: Literal["draft_delta"] = "draft_delta"
    field: Literal["subject", "body"]
    delta: str


class Reviewed(Payload):
    type: Literal["review"] = "review"
    attempt: int
    passed: bool
    issues: list[str]


class RunUsage(Payload):
    input: int | None
    cached_input: int | None
    output: int | None
    reasoning: int | None
    model_usd: float | None
    search_usd: float | None
    duration_seconds: float | None
    model: str


class Completed(Payload):
    type: Literal["completed"] = "completed"
    outcome: Literal["ready", "needs_attention"]
    issues: list[str]
    usage: RunUsage | None
    elapsed_ms: int | None = None


class Failed(Payload):
    type: Literal["failed"] = "failed"
    reason: FailureReason
    message: str
    stage: Stage | None
    elapsed_ms: int | None = None


def emit(payload: Payload) -> None:
    """Publish a payload from inside a graph node."""
    get_stream_writer()(payload)


def to_wire(payload: Payload, run_id: str, sequence: int) -> dict:
    return {**payload.model_dump(by_alias=True, mode="json"), "runId": run_id, "sequence": sequence}
