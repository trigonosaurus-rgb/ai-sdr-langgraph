"""Structured LLM calls with usage taken from API metadata."""

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from core.config import Settings
from core.schemas import Stage, Usage

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The call failed or returned no valid structured output. usage is set if the API reported it."""

    def __init__(self, message: str, usage: Usage | None = None, model: str | None = None):
        super().__init__(message)
        self.usage = usage or Usage()
        self.model = model


@dataclass
class LLMReply(Generic[T]):
    parsed: T
    usage: Usage
    model: str


class StructuredLLM(Protocol):
    def generate(self, stage: Stage, schema: type[T], system: str, user: str) -> LLMReply[T]: ...


def usage_from_metadata(metadata: dict[str, Any] | None) -> Usage:
    """Map LangChain usage_metadata to Usage; anything not reported stays None."""
    if not metadata:
        return Usage()
    input_details = metadata.get("input_token_details") or {}
    output_details = metadata.get("output_token_details") or {}
    return Usage(
        input_tokens=metadata.get("input_tokens"),
        cached_input_tokens=input_details.get("cache_read"),
        output_tokens=metadata.get("output_tokens"),
        reasoning_tokens=output_details.get("reasoning"),
    )


class OpenAILLM:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._clients: dict[Stage, ChatOpenAI] = {}

    def _client(self, stage: Stage) -> ChatOpenAI:
        if stage not in self._clients:
            cfg = self.settings.models[stage]
            kwargs: dict[str, Any] = {
                "model": cfg.model,
                "timeout": self.settings.llm_timeout_s,
                "max_retries": self.settings.llm_max_retries,
            }
            if cfg.reasoning_effort is not None:
                kwargs["reasoning_effort"] = cfg.reasoning_effort
            if cfg.temperature is not None:
                kwargs["temperature"] = cfg.temperature
            self._clients[stage] = ChatOpenAI(**kwargs)
        return self._clients[stage]

    def generate(self, stage: Stage, schema: type[T], system: str, user: str) -> LLMReply[T]:
        model = self.settings.models[stage].model
        chain = self._client(stage).with_structured_output(
            schema, method="json_schema", strict=True, include_raw=True
        )
        try:
            out = chain.invoke([("system", system), ("user", user)])
        except Exception as error:  # network, auth, rate limit after retries
            raise LLMError(f"{type(error).__name__}: {error}", model=model) from error
        raw = out["raw"]
        usage = usage_from_metadata(getattr(raw, "usage_metadata", None))
        model = (getattr(raw, "response_metadata", None) or {}).get("model_name") or model
        if out.get("parsing_error") is not None or out.get("parsed") is None:
            refusal = (getattr(raw, "additional_kwargs", None) or {}).get("refusal")
            reason = refusal or out.get("parsing_error") or "empty response"
            raise LLMError(f"No valid {schema.__name__}: {reason}", usage=usage, model=model)
        return LLMReply(parsed=out["parsed"], usage=usage, model=model)
