"""Fakes and canned replies: tests never touch the network."""

from dataclasses import dataclass, field

from langchain_core.utils.json import parse_partial_json
from pydantic import BaseModel

from core.config import Settings
from core.context import RunContext
from core.llm import LLMReply
from core.schemas import (
    Brief,
    Draft,
    ExtractedFact,
    ResearchOutput,
    Review,
    SearchResult,
    Strategy,
    Usage,
)
from core.search import SearchResponse

USAGE = Usage(input_tokens=100, cached_input_tokens=20, output_tokens=50, reasoning_tokens=10)


@dataclass
class Call:
    stage: str
    system: str
    user: str


class FakeLLM:
    """Replies scripted per stage, consumed in order. An Exception in the script is raised.
    When streamed, the reply's JSON arrives in chunk_chars pieces, like tokens."""

    def __init__(
        self,
        script: dict[str, list[BaseModel | Exception]],
        usage: Usage = USAGE,
        chunk_chars: int = 4,
        model: str = "fake-model",
    ):
        self.script = {stage: list(replies) for stage, replies in script.items()}
        self.usage = usage
        self.model = model
        self.chunk_chars = chunk_chars
        self.calls: list[Call] = []

    def generate(self, stage, schema, system, user, on_partial=None):
        self.calls.append(Call(stage, system, user))
        reply = self.script[stage].pop(0)
        if isinstance(reply, Exception):
            raise reply
        assert isinstance(reply, schema)
        if on_partial is not None:
            text = reply.model_dump_json()
            for end in range(self.chunk_chars, len(text) + self.chunk_chars, self.chunk_chars):
                if isinstance(partial := parse_partial_json(text[:end]), dict):
                    on_partial(partial)
        return LLMReply(parsed=reply, usage=self.usage, model=self.model)

    def stages(self) -> list[str]:
        return [call.stage for call in self.calls]


@dataclass
class FakeSearch:
    official: list[SearchResult] = field(default_factory=list)
    web: list[SearchResult] = field(default_factory=list)
    news: list[SearchResult] = field(default_factory=list)
    error: Exception | None = None
    queries: list[tuple[str, str, list[str] | None]] = field(default_factory=list)

    def search(self, query, *, topic="general", include_domains=None, max_results=5):
        self.queries.append((query, topic, include_domains))
        if self.error:
            raise self.error
        if include_domains:
            results = self.official
        elif topic == "news":
            results = self.news
        else:
            results = self.web
        return SearchResponse(results=results[:max_results], credits=1)


class FakeClock:
    def __init__(self, step: float = 0.25):
        self.now, self.step = 0.0, step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


ABOUT = (
    "Acme builds route planning software for regional delivery fleets. "
    "More than 400 logistics companies across Europe use Acme Routes every day."
)
NEWS = "Acme opened an office in Warsaw in March and is hiring 30 engineers for its new analytics team."


def source(url: str, title: str, content: str) -> SearchResult:
    return SearchResult(url=url, title=title, content=content, query="q")


def research_output(**overrides) -> ResearchOutput:
    values = dict(
        website_owner="Acme",
        website_matches=True,
        website_note="The official site and news describe the same company.",
        facts=[
            ExtractedFact(
                claim="Acme sells route planning software to delivery fleets.",
                source_id=1,
                excerpt="Acme builds route planning software for regional delivery fleets",
            ),
            ExtractedFact(
                claim="Acme is hiring 30 engineers for a new analytics team.",
                source_id=2,
                excerpt="hiring 30 engineers for its new analytics team",
            ),
        ],
        sufficient=True,
        gaps="",
    )
    return ResearchOutput(**{**values, **overrides})


def strategy(**overrides) -> Strategy:
    values = dict(
        observation="Acme is building a new analytics team in Warsaw.",
        fact_ids=[2, 99],
        offer_link="Contract data engineers can help the new team ship before hiring completes.",
        hypotheses=["Hiring 30 engineers may take longer than planned."],
        angle="Ask how the Warsaw analytics team is staffing up.",
        offer_fit="good",
        fit_reason="They are actively growing a data team.",
    )
    return Strategy(**{**values, **overrides})


def draft(n: int = 1) -> Draft:
    return Draft(subject=f"Warsaw analytics team {n}", body=f"Body of draft {n}.")


PASS = Review(passed=True, issues=[])


def reject(issue: str = "Too salesy in the second line.") -> Review:
    return Review(passed=False, issues=[issue])


def happy_script(**stages) -> dict:
    script = {
        "Research": [research_output()],
        "Strategy": [strategy()],
        "Writing": [draft(1)],
        "Review": [PASS],
    }
    script.update(stages)
    return script
