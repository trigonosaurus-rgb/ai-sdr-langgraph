"""OpenAILLM against a mocked Chat Completions endpoint: streaming, usage and failures, no network."""

import json

import httpx2
import pytest

from core.config import Settings
from core.llm import LLMError, OpenAILLM
from core.schemas import Draft, Usage

MODEL = "gpt-5.4-mini-2026-03-17"
USAGE = {
    "prompt_tokens": 100,
    "completion_tokens": 40,
    "total_tokens": 140,
    "prompt_tokens_details": {"cached_tokens": 10},
    "completion_tokens_details": {"reasoning_tokens": 12},
}


def sse(chunks: list[dict]) -> bytes:
    base = {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": MODEL}
    lines = [f"data: {json.dumps({**base, **chunk})}\n\n" for chunk in chunks]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


def delta(**fields) -> dict:
    return {"choices": [{"index": 0, "delta": fields, "finish_reason": None}]}


def stream_of(content: str, *, piece: int = 6, finish: str = "stop", usage: dict = USAGE) -> bytes:
    chunks = [delta(role="assistant", content="")]
    chunks += [delta(content=content[i : i + piece]) for i in range(0, len(content), piece)]
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    chunks.append({"choices": [], "usage": usage})  # sent because stream_options.include_usage is on
    return sse(chunks)


class Endpoint:
    def __init__(self, body: bytes, status: int = 200):
        self.body, self.status, self.requests = body, status, []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        return httpx2.Response(self.status, headers={"content-type": "text/event-stream"}, content=self.body)


def make_llm(endpoint: Endpoint) -> OpenAILLM:
    client = httpx2.Client(transport=httpx2.MockTransport(endpoint))
    return OpenAILLM(Settings(llm_max_retries=0), http_client=client)


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_stream_reports_partials_and_takes_usage_once():
    content = json.dumps({"subject": "Warsaw team", "body": "Hello there.\nSecond line."})
    endpoint = Endpoint(stream_of(content))
    partials: list[dict] = []

    reply = make_llm(endpoint).generate("Writing", Draft, "system", "user", on_partial=partials.append)

    assert reply.parsed == Draft(subject="Warsaw team", body="Hello there.\nSecond line.")
    assert reply.usage == Usage(input_tokens=100, cached_input_tokens=10, output_tokens=40, reasoning_tokens=12)
    assert reply.model == MODEL
    assert len(partials) > 3 and partials[-1] == reply.parsed.model_dump()
    bodies = [p["body"] for p in partials if "body" in p]
    assert all(later.startswith(earlier) for earlier, later in zip(bodies, bodies[1:]))

    request = endpoint.requests[0]
    assert request["stream"] is True and request["stream_options"] == {"include_usage": True}
    assert request["reasoning_effort"] == "medium"
    schema = request["response_format"]["json_schema"]
    assert schema["strict"] is True and schema["schema"]["required"] == ["subject", "body"]


def test_cache_writes_are_taken_from_usage():
    usage = {**USAGE, "prompt_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 70}}
    endpoint = Endpoint(stream_of(json.dumps({"subject": "S", "body": "B"}), usage=usage))

    reply = make_llm(endpoint).generate("Writing", Draft, "system", "user", on_partial=lambda _: None)

    assert reply.usage.cached_input_tokens == 10 and reply.usage.cache_write_tokens == 70


def test_refusal_is_an_error_with_usage():
    endpoint = Endpoint(stream_of("", finish="stop").replace(b'"content": ""', b'"refusal": "I cannot help."', 1))
    with pytest.raises(LLMError, match="I cannot help") as caught:
        make_llm(endpoint).generate("Writing", Draft, "s", "u", on_partial=lambda _: None)
    assert caught.value.usage.input_tokens == 100


def test_truncated_json_is_an_error_with_usage():
    endpoint = Endpoint(stream_of('{"subject": "Hi", "body": "cut of', finish="length"))
    with pytest.raises(LLMError, match="length limit") as caught:
        make_llm(endpoint).generate("Writing", Draft, "s", "u", on_partial=lambda _: None)
    assert caught.value.usage.output_tokens == 40 and caught.value.model == MODEL


def test_http_error_is_an_llm_error():
    endpoint = Endpoint(b'{"error": {"message": "boom", "type": "server_error"}}', status=500)
    with pytest.raises(LLMError, match="500"):
        make_llm(endpoint).generate("Writing", Draft, "s", "u", on_partial=lambda _: None)


def completion(content: str, finish: str = "stop") -> bytes:
    return json.dumps(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 1,
            "model": MODEL,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}
            ],
            "usage": USAGE,
        }
    ).encode()


def test_structured_call_without_streaming():
    endpoint = Endpoint(completion(json.dumps({"subject": "Hi", "body": "Text."})))
    reply = make_llm(endpoint).generate("Review", Draft, "s", "u")
    assert reply.parsed == Draft(subject="Hi", body="Text.")
    assert reply.usage.input_tokens == 100 and reply.usage.reasoning_tokens == 12
    assert not endpoint.requests[0].get("stream") and endpoint.requests[0]["reasoning_effort"] == "low"


def test_length_limit_without_streaming_keeps_usage():
    endpoint = Endpoint(completion('{"subject": "Hi", "bo', finish="length"))
    with pytest.raises(LLMError) as caught:
        make_llm(endpoint).generate("Review", Draft, "s", "u")
    assert caught.value.usage.output_tokens == 40
