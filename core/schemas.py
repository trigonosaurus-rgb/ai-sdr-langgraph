"""Data shapes shared by the graph, the runner and (later) the API."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

Language = Literal["English", "Russian"]
Tone = Literal["Direct", "Warm"]
Stage = Literal["Research", "Strategy", "Writing", "Review"]
Outcome = Literal["ready", "needs_attention", "failed"]
FailureReason = Literal["insufficient_data", "website_mismatch", "cancelled", "daily_limit", "error"]


def domain_of(url: str) -> str:
    """Bare host of a URL or domain: 'https://www.Acme.com/about' -> 'acme.com'."""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


class Brief(BaseModel):
    """Everything the user tells us about the outreach."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company: str = Field(min_length=1, max_length=200)
    website: str = Field(min_length=1, max_length=500)
    offer: str = Field(min_length=1, max_length=2000)
    recipient: str = Field(min_length=1, max_length=200)
    language: Language = "English"
    tone: Tone = "Direct"

    @field_validator("website")
    @classmethod
    def website_has_domain(cls, value: str) -> str:
        if "." not in domain_of(value):
            raise ValueError("website must be a domain or URL, e.g. acme.com")
        return value

    @computed_field
    @property
    def domain(self) -> str:
        return domain_of(self.website)


class SearchResult(BaseModel):
    url: str
    title: str
    content: str
    query: str


# --- Structured LLM outputs. All fields are required: OpenAI strict schemas demand it.


class ExtractedFact(BaseModel):
    claim: str = Field(description="One specific, checkable statement about the company.")
    source_id: int = Field(description="Number of the search result that states this claim.")
    excerpt: str = Field(
        description="Short verbatim quote (under 300 characters) from that result supporting the claim."
    )


class ResearchOutput(BaseModel):
    website_matches: bool = Field(
        description="True if the results describe the company that owns the given website."
    )
    website_note: str = Field(description="One sentence explaining the website verdict.")
    facts: list[ExtractedFact]
    sufficient: bool = Field(
        description="True if the facts are enough to write a specific, non-generic email."
    )
    gaps: str = Field(description="What important information is missing; empty if nothing.")


class Strategy(BaseModel):
    observation: str = Field(description="The single most relevant observation about the company.")
    fact_ids: list[int] = Field(description="Ids of the facts the observation relies on.")
    offer_link: str = Field(description="How the sender's offer connects to that observation.")
    hypotheses: list[str] = Field(
        description="Assumptions not confirmed by the facts, phrased as hypotheses."
    )
    angle: str = Field(description="How to open the email in one sentence.")
    offer_fit: Literal["good", "weak", "poor"]
    fit_reason: str = Field(description="Why the offer fits or does not fit this company.")


class Draft(BaseModel):
    subject: str
    body: str


class Review(BaseModel):
    passed: bool
    issues: list[str] = Field(description="Concrete problems to fix; empty when passed.")


# --- Pipeline records


class Fact(BaseModel):
    id: int
    claim: str
    excerpt: str
    source_url: str
    source_title: str


class Research(BaseModel):
    facts: list[Fact]
    website_matches: bool
    website_note: str
    site_indexed: bool  # at least one result came from the brief's domain
    sufficient: bool
    gaps: str
    dropped_facts: int  # extracted facts discarded because their quote was not in the source


class Usage(BaseModel):
    """Token counts from API metadata; None when the provider did not report them."""

    input_tokens: int | None = None
    cached_input_tokens: int | None = None  # subset of input_tokens
    output_tokens: int | None = None
    reasoning_tokens: int | None = None  # subset of output_tokens


class LLMCall(BaseModel):
    stage: Stage
    attempt: int
    model: str
    prompt_version: str
    duration_ms: int
    usage: Usage
    cost_usd: float | None = None  # fixed when recorded; None: unknown model or usage
    price_version: str | None = None
    error: str | None = None


class SearchCall(BaseModel):
    query: str
    topic: str
    results: int
    credits: float | None  # as reported by Tavily; None if not reported
    duration_ms: int
    cost_usd: float | None = None  # fixed when recorded; None when credits are unknown
    price_version: str | None = None
    error: str | None = None


class Attempt(BaseModel):
    attempt: int
    draft: Draft
    review: Review | None = None


class RunResult(BaseModel):
    run_id: str
    brief: Brief
    status: Outcome
    reason: FailureReason | None = None
    message: str
    issues: list[str]
    research: Research | None
    strategy: Strategy | None
    draft: Draft | None
    attempts: list[Attempt]
    prompt_versions: dict[str, str]
    llm_calls: list[LLMCall]
    search_calls: list[SearchCall]
    duration_ms: int
