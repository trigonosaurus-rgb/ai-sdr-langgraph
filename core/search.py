"""Web search behind a small interface so tests can swap it out."""

import os
from dataclasses import dataclass
from typing import Literal, Protocol

from tavily import TavilyClient

from core.schemas import SearchResult

Topic = Literal["general", "news"]


class SearchError(Exception):
    pass


@dataclass
class SearchResponse:
    results: list[SearchResult]
    credits: float | None  # None when the provider did not report usage


class SearchClient(Protocol):
    def search(
        self,
        query: str,
        *,
        topic: Topic = "general",
        include_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> SearchResponse: ...


class TavilySearch:
    def __init__(self, api_key: str | None = None):
        self.client = TavilyClient(api_key=api_key or os.environ["TAVILY_API_KEY"])

    def search(
        self,
        query: str,
        *,
        topic: Topic = "general",
        include_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> SearchResponse:
        try:
            data = self.client.search(
                query,
                search_depth="basic",
                topic=topic,
                time_range="year" if topic == "news" else None,
                max_results=max_results,
                include_domains=include_domains,
                include_usage=True,
            )
        except Exception as error:
            raise SearchError(f"{type(error).__name__}: {error}") from error
        results = [
            SearchResult(
                url=item["url"],
                title=item.get("title") or item["url"],
                content=item.get("content") or "",
                query=query,
            )
            for item in data.get("results", [])
            if item.get("url")
        ]
        credits = (data.get("usage") or {}).get("credits")
        return SearchResponse(results=results, credits=credits)
