"""Per-run dependencies and the log of every paid call, including failed ones."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from pydantic import BaseModel

from core.config import Settings
from core.llm import PartialHandler, StructuredLLM
from core.pricing import PRICES, PriceTable
from core.prompts import Prompt
from core.schemas import LLMCall, SearchCall, SearchResult, Stage, Usage
from core.search import SearchClient, Topic

T = TypeVar("T", bound=BaseModel)
CallKind = Literal["llm", "search"]


class RunCancelled(Exception):
    """The run was cancelled; raised before a paid call so nothing more is spent."""


class BudgetExhausted(Exception):
    """The service budget for the month is spent; raised before a paid call."""


@dataclass
class RunContext:
    settings: Settings
    llm: StructuredLLM
    search_client: SearchClient
    clock: Callable[[], float] = time.monotonic  # seconds
    cancel: threading.Event | None = None  # set from another thread to stop before the next paid call
    prices: PriceTable = PRICES
    # Called before each paid call; raises BudgetExhausted to stop the run.
    before_call: Callable[[CallKind], None] | None = None
    # Called with each recorded call, failed ones included, as soon as it ends.
    on_record: Callable[[LLMCall | SearchCall], None] | None = None
    llm_calls: list[LLMCall] = field(default_factory=list)
    search_calls: list[SearchCall] = field(default_factory=list)

    def check_cancelled(self) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise RunCancelled

    def _before(self, kind: CallKind) -> None:
        self.check_cancelled()
        if self.before_call is not None:
            self.before_call(kind)

    def _record_llm(self, model: str, usage: Usage, **fields) -> None:
        call = LLMCall(
            model=model,
            usage=usage,
            cost_usd=self.prices.llm_cost(model, usage),
            price_version=self.prices.version,
            **fields,
        )
        self.llm_calls.append(call)
        if self.on_record is not None:
            self.on_record(call)

    def _record_search(self, credits: float | None, **fields) -> None:
        call = SearchCall(
            credits=credits,
            cost_usd=self.prices.search_cost(credits),
            price_version=self.prices.version,
            **fields,
        )
        self.search_calls.append(call)
        if self.on_record is not None:
            self.on_record(call)

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
        on_partial: PartialHandler | None = None,
    ) -> T:
        self._before("llm")
        start = self.clock()
        model = self.settings.models[stage].model
        try:
            reply = self.llm.generate(stage, schema, system, user, on_partial)
        except Exception as error:
            self._record_llm(
                getattr(error, "model", None) or model,
                getattr(error, "usage", None) or Usage(),
                stage=stage,
                attempt=attempt,
                prompt_version=prompt.tag,
                duration_ms=self._ms_since(start),
                error=str(error),
            )
            raise
        self._record_llm(
            reply.model,
            reply.usage,
            stage=stage,
            attempt=attempt,
            prompt_version=prompt.tag,
            duration_ms=self._ms_since(start),
        )
        return reply.parsed

    def search(
        self,
        query: str,
        *,
        topic: Topic = "general",
        include_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        self._before("search")
        start = self.clock()
        try:
            response = self.search_client.search(
                query,
                topic=topic,
                include_domains=include_domains,
                max_results=self.settings.search_results_per_query,
            )
        except Exception as error:
            self._record_search(
                None, query=query, topic=topic, results=0, duration_ms=self._ms_since(start), error=str(error)
            )
            raise
        self._record_search(
            response.credits,
            query=query,
            topic=topic,
            results=len(response.results),
            duration_ms=self._ms_since(start),
        )
        return response.results
