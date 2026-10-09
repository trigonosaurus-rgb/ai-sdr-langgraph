"""Structured LLM calls with usage taken from API metadata."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.utils.json import parse_partial_json
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from core.config import Settings
from core.schemas import Stage, Usage

T = TypeVar("T", bound=BaseModel)
PartialHandler = Callable[[dict[str, Any]], None]  # receives the object parsed so far


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
    def generate(
        self,
        stage: Stage,
        schema: type[T],
        system: str,
        user: str,
        on_partial: PartialHandler | None = None,
    ) -> LLMReply[T]:
        """With on_partial the reply is streamed and on_partial sees each partial object."""
        ...


def usage_from_metadata(metadata: dict[str, Any] | None) -> Usage:
    """Map LangChain usage_metadata to Usage; anything not reported stays None."""
    if not metadata:
        return Usage()
    input_details = metadata.get("input_token_details") or {}
    output_details = metadata.get("output_token_details") or {}
    return Usage(
        input_tokens=metadata.get("input_tokens"),
        cached_input_tokens=input_details.get("cache_read"),
        cache_write_tokens=input_details.get("cache_creation"),
        output_tokens=metadata.get("output_tokens"),
        reasoning_tokens=output_details.get("reasoning"),
    )


def usage_from_error(error: Exception) -> Usage:
    """Usage the API reported before failing, e.g. a reply cut at the length limit was still billed."""
    completion = getattr(error, "completion", None)
    usage = getattr(completion, "usage", None)
    if usage is None:
        return Usage()
    input_details = getattr(usage, "prompt_tokens_details", None)
    output_details = getattr(usage, "completion_tokens_details", None)
    return Usage(
        input_tokens=usage.prompt_tokens,
        cached_input_tokens=getattr(input_details, "cached_tokens", None),
        cache_write_tokens=getattr(input_details, "cache_write_tokens", None),
        output_tokens=usage.completion_tokens,
        reasoning_tokens=getattr(output_details, "reasoning_tokens", None),
    )


def _call_error(error: Exception, model: str) -> LLMError:
    completion = getattr(error, "completion", None)
    model = getattr(completion, "model", None) or model
    return LLMError(f"{type(error).__name__}: {error}", usage=usage_from_error(error), model=model)


class OpenAILLM:
    def __init__(self, settings: Settings, http_client: Any = None):
        self.settings = settings
        self.http_client = http_client  # tests pass one with a mock transport
        self._clients: dict[Stage, ChatOpenAI] = {}

    def _client(self, stage: Stage) -> ChatOpenAI:
        if stage not in self._clients:
            cfg = self.settings.models[stage]
            kwargs: dict[str, Any] = {
                "model": cfg.model,
                "timeout": self.settings.llm_timeout_s,
                "max_retries": self.settings.llm_max_retries,
                "stream_usage": True,  # otherwise only on by default with the default client
            }
            if self.http_client is not None:
                kwargs["http_client"] = self.http_client
            if cfg.reasoning_effort is not None:
                kwargs["reasoning_effort"] = cfg.reasoning_effort
            if cfg.temperature is not None:
                kwargs["temperature"] = cfg.temperature
            self._clients[stage] = ChatOpenAI(**kwargs)
        return self._clients[stage]

    def generate(
        self,
        stage: Stage,
        schema: type[T],
        system: str,
        user: str,
        on_partial: PartialHandler | None = None,
    ) -> LLMReply[T]:
        if on_partial is not None:
            return self._stream(stage, schema, system, user, on_partial)
        model = self.settings.models[stage].model
        chain = self._client(stage).with_structured_output(
            schema, method="json_schema", strict=True, include_raw=True
        )
        try:
            out = chain.invoke([("system", system), ("user", user)])
        except Exception as error:  # network, auth, rate limit after retries, length limit
            raise _call_error(error, model) from error
        raw = out["raw"]
        usage = usage_from_metadata(getattr(raw, "usage_metadata", None))
        model = (getattr(raw, "response_metadata", None) or {}).get("model_name") or model
        if out.get("parsing_error") is not None or out.get("parsed") is None:
            refusal = (getattr(raw, "additional_kwargs", None) or {}).get("refusal")
            reason = refusal or out.get("parsing_error") or "empty response"
            raise LLMError(f"No valid {schema.__name__}: {reason}", usage=usage, model=model)
        return LLMReply(parsed=out["parsed"], usage=usage, model=model)

    def _stream(
        self, stage: Stage, schema: type[T], system: str, user: str, on_partial: PartialHandler
    ) -> LLMReply[T]:
        """Stream a strict JSON-schema reply. The schema goes as a plain dict and the JSON is parsed
        here: passing the model class makes the SDK attach a typed `parsed` that pydantic warns about."""
        model = self.settings.models[stage].model
        function = convert_to_openai_function(schema, strict=True)
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": function["name"], "schema": function["parameters"], "strict": True},
        }
        text, usage_metadata, refusal = "", None, None
        try:
            chunks = iter(
                self._client(stage).stream([("system", system), ("user", user)], response_format=response_format)
            )
        except Exception as error:
            raise _call_error(error, model) from error
        while True:
            try:
                chunk = next(chunks, None)
            except Exception as error:  # network, auth, rate limit after retries, length limit, dropped stream
                raise _call_error(error, model) from error
            if chunk is None:
                break
            if isinstance(chunk.content, str) and chunk.content:
                text += chunk.content
                partial = parse_partial_json(text)
                if isinstance(partial, dict):
                    on_partial(partial)
            # Usage arrives once, with the final completion; take it, never sum chunks.
            usage_metadata = chunk.usage_metadata or usage_metadata
            model = chunk.response_metadata.get("model_name") or model
            refusal = chunk.additional_kwargs.get("refusal") or refusal

        usage = usage_from_metadata(usage_metadata)
        if refusal:
            raise LLMError(f"No valid {schema.__name__}: {refusal}", usage=usage, model=model)
        try:
            parsed = schema.model_validate_json(text)
        except ValidationError as error:
            reason = "empty response" if not text else error
            raise LLMError(f"No valid {schema.__name__}: {reason}", usage=usage, model=model) from error
        return LLMReply(parsed=parsed, usage=usage, model=model)
