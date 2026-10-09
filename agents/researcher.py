"""Research: several searches, then facts with verified quotes and a sufficiency verdict."""

import re
from urllib.parse import urlsplit

from core.context import RunContext
from core.events import Activity, Evidence, EvidenceItem, StageStarted, emit
from core.prompts import load_prompt
from core.schemas import Brief, ExtractedFact, Fact, Research, ResearchOutput, SearchResult, domain_of
from core.state import SDRState

MAX_FACTS = 8


def search_queries(brief: Brief) -> list[tuple[str, dict]]:
    """(query, options) pairs: the official site, the open web, recent news."""
    name = f'"{brief.company}"'
    return [
        (f"{name} company overview products customers", {"include_domains": [brief.domain]}),
        (f"{name} {brief.domain}", {}),
        (f"{name} news", {"topic": "news"}),
    ]


def is_official(url: str, domain: str) -> bool:
    host = domain_of(url)
    return host == domain or host.endswith("." + domain)


def _url_key(url: str) -> str:
    parts = urlsplit(url)
    return f"{domain_of(url)}{parts.path.rstrip('/')}?{parts.query}"


def collect_sources(ctx: RunContext, brief: Brief) -> list[SearchResult]:
    """Run all queries; official-site pages first, duplicates removed."""
    seen: set[str] = set()
    sources: list[SearchResult] = []
    for query, options in search_queries(brief):
        for result in ctx.search(query, **options):
            key = _url_key(result.url)
            if key not in seen:
                seen.add(key)
                sources.append(result)
    sources.sort(key=lambda source: not is_official(source.url, brief.domain))
    return sources


def _normalize(text: str) -> str:
    text = text.lower()
    for fancy, plain in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), ("–", "-"), ("—", "-")):
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def quote_in_source(excerpt: str, content: str) -> bool:
    quote = _normalize(excerpt).strip(" .\"'")
    return len(quote) >= 12 and quote in _normalize(content)


def display_path(url: str) -> str:
    parts = urlsplit(url)
    return (domain_of(url) + parts.path.rstrip("/"))[:80]


def make_researcher(ctx: RunContext):
    prompt = load_prompt("research")

    def researcher(state: SDRState) -> dict:
        brief = state["brief"]
        emit(StageStarted(stage="Research", message=f"Searching the web for {brief.company}"))
        sources = collect_sources(ctx, brief)
        official = sum(is_official(source.url, brief.domain) for source in sources)
        emit(Activity(message=f"Found {len(sources)} pages, {official} from {brief.domain}"))

        if not sources:
            research = Research(
                facts=[],
                website_matches=False,
                website_note="Search returned nothing.",
                site_indexed=False,
                sufficient=False,
                gaps="No search results.",
                dropped_facts=0,
            )
            return {"research": research, "stop": "insufficient_data"}

        texts = [source.content[: ctx.settings.source_chars] for source in sources]
        listing = "\n\n".join(
            f"[{i}] {source.title}{' (official site)' if is_official(source.url, brief.domain) else ''}\n"
            f"URL: {source.url}\n{text}"
            for i, (source, text) in enumerate(zip(sources, texts), start=1)
        )
        output = ctx.ask(
            "Research",
            1,
            prompt,
            ResearchOutput,
            prompt.render("system"),
            prompt.render("user", company=brief.company, domain=brief.domain, sources=listing),
        )

        facts: list[Fact] = []
        dropped: list[ExtractedFact] = []
        for extracted in output.facts:
            index = extracted.source_id - 1
            if not 0 <= index < len(sources) or not quote_in_source(extracted.excerpt, texts[index]):
                dropped.append(extracted)
                continue
            facts.append(
                Fact(
                    id=len(facts) + 1,
                    claim=extracted.claim,
                    excerpt=extracted.excerpt,
                    source_url=sources[index].url,
                    source_title=sources[index].title,
                )
            )
            if len(facts) == MAX_FACTS:
                break

        research = Research(
            facts=facts,
            website_matches=output.website_matches,
            website_note=output.website_note,
            site_indexed=official > 0,
            sufficient=output.sufficient and len(facts) >= ctx.settings.min_facts,
            gaps=output.gaps,
            dropped_facts=len(dropped),
            dropped=dropped,
        )
        emit(Activity(message=f"Kept {len(facts)} facts with verified quotes"))
        if facts:
            emit(
                Evidence(
                    sources=[
                        EvidenceItem(
                            id=fact.id,
                            claim=fact.claim,
                            title=fact.source_title,
                            url=fact.source_url,
                            path=display_path(fact.source_url),
                            excerpt=fact.excerpt,
                        )
                        for fact in facts
                    ]
                )
            )

        update: dict = {"research": research, "prompt_versions": {prompt.name: prompt.tag}}
        if not research.website_matches:
            update["stop"] = "website_mismatch"
        elif not research.sufficient:
            update["stop"] = "insufficient_data"
        return update

    return researcher
