"""Per-run dependencies and the log of every paid call, including failed ones."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from core.config import Settings
from core.llm import StructuredLLM
from core.prompts import Prompt
from core.schemas import LLMCall, SearchCall, SearchResult, Stage, Usage
from core.search import SearchClient, Topic

T = TypeVar("T", bound=BaseModel)


@dataclass
class RunContext:
    settings: Settings
    llm: StructuredLLM
    search_client: SearchClient
    clock: Callable[[], float] = time.monotonic  # seconds
    llm_calls: list[LLMCall] = field(default_factory=list)
    search_calls: list[SearchCall] = field(default_factory=list)

    def _ms_since(self, start: float) -> int:
        return round((self.clock() - start) * 1000)

    def ask(
        self,
        stage: Stage,
        attempt: int,
        prompt: Prompt,
        schema: type[T],
        system: str,
        user: str,
    ) -> T:
        start = self.clock()
        model = self.settings.models[stage].model
        try:
            reply = self.llm.generate(stage, schema, system, user)
        except Exception as error:
            self.llm_calls.append(
                LLMCall(
                    stage=stage,
                    attempt=attempt,
                    model=getattr(error, "model", None) or model,
                    prompt_version=prompt.tag,
                    duration_ms=self._ms_since(start),
                    usage=getattr(error, "usage", None) or Usage(),
                    error=str(error),
                )
            )
            raise
        self.llm_calls.append(
            LLMCall(
                stage=stage,
                attempt=attempt,
                model=reply.model,
                prompt_version=prompt.tag,
                duration_ms=self._ms_since(start),
                usage=reply.usage,
            )
        )
        return reply.parsed

    def search(
        self,
        query: str,
        *,
        topic: Topic = "general",
        include_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        start = self.clock()
        try:
            response = self.search_client.search(
                query,
                topic=topic,
                include_domains=include_domains,
                max_results=self.settings.search_results_per_query,
            )
        except Exception as error:
            self.search_calls.append(
                SearchCall(
                    query=query,
                    topic=topic,
                    results=0,
                    credits=None,
                    duration_ms=self._ms_since(start),
                    error=str(error),
                )
            )
            raise
        self.search_calls.append(
            SearchCall(
                query=query,
                topic=topic,
                results=len(response.results),
                credits=response.credits,
                duration_ms=self._ms_since(start),
            )
        )
        return response.results
