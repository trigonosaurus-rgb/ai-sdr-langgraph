"""Small pieces: brief validation, quote checks, prompts, usage mapping, the OpenAI wrapper."""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from agents.researcher import quote_in_source
from core.config import Settings
from core.llm import LLMError, OpenAILLM, usage_from_metadata
from core.prompts import PROMPTS_DIR, load_prompt, parse_prompt
from core.schemas import Brief, Draft, domain_of


@pytest.mark.parametrize(
    ("url", "domain"),
    [
        ("https://www.Acme.com/about?x=1", "acme.com"),
        ("acme.com", "acme.com"),
        ("http://shop.acme.co.uk", "shop.acme.co.uk"),
    ],
)
def test_domain_of(url, domain):
    assert domain_of(url) == domain


def test_brief_rejects_missing_fields_and_bad_website():
    base = dict(company="Acme", website="acme.com", offer="x", recipient="CTO")
    assert Brief(**base).domain == "acme.com"
    with pytest.raises(ValidationError):
        Brief(**{**base, "website": "not a site"})
    with pytest.raises(ValidationError):
        Brief(**{**base, "offer": "   "})
    with pytest.raises(ValidationError):
        Brief(**{**base, "language": "German"})


def test_quote_must_appear_in_the_source():
    content = "Acme’s platform serves  400\ncustomers — mostly fleets."
    assert quote_in_source("Acme's platform serves 400 customers - mostly fleets", content)
    assert quote_in_source('"platform serves 400 customers."', content)
    assert not quote_in_source("platform serves 500 customers", content)
    assert not quote_in_source("Acme", content)  # too short to prove anything


def test_quote_check_accepts_russian_typography_and_ellipsis_cuts():
    content = "Контур — экосистема для бизнеса. Управление HR\u2011процессами и всё для отчётности."
    assert quote_in_source("«Контур - экосистема для бизнеса»", content)  # guillemets, plain dash
    assert quote_in_source("„Управление HR-процессами и все для отчетности“", content)  # non-breaking hyphen, ё
    assert quote_in_source("«Контур — экосистема для бизнеса… Управление HR-процессами»", content)
    assert not quote_in_source("Контур — экосистема для бизнеса… и не только", content)  # every part must match
    assert not quote_in_source("Контур — экосистема для бизнеса … Контур", content)  # each part long enough


def test_every_prompt_has_a_version_and_renders():
    names = sorted(p.stem for p in PROMPTS_DIR.glob("*.md"))
    assert names == ["copywriter", "research", "review", "strategy"]
    for name in names:
        prompt = load_prompt(name)
        assert prompt.tag == f"{name}@{prompt.version}"
    values = dict(
        company="A",
        domain="a.com",
        sources="s",
        recipient="r",
        offer="o",
        facts="f",
        strategy="s",
        language="English",
        tone_guide="t",
        subject="s",
        body="b",
        previous_subject="p",
        previous_body="p",
        issues="i",
    )
    for name in names:
        for section in load_prompt(name).sections:
            assert "$" not in load_prompt(name).render(section, **values)


def test_prompt_without_version_is_rejected():
    with pytest.raises(ValueError, match="version"):
        parse_prompt("x", "---\nauthor: me\n---\n# system\na\n# user\nb\n")
    with pytest.raises(ValueError, match="front matter"):
        parse_prompt("x", "# system\na\n# user\nb\n")


def test_usage_mapping_keeps_unknown_as_none():
    assert usage_from_metadata(None).input_tokens is None
    usage = usage_from_metadata(
        {
            "input_tokens": 120,
            "output_tokens": 40,
            "input_token_details": {"cache_read": 100},
            "output_token_details": {"reasoning": 30},
        }
    )
    assert (usage.input_tokens, usage.cached_input_tokens) == (120, 100)
    assert (usage.output_tokens, usage.reasoning_tokens) == (40, 30)
    partial = usage_from_metadata({"input_tokens": 5, "output_tokens": 6})
    assert partial.cached_input_tokens is None and partial.reasoning_tokens is None


class _FakeChat:
    """Stands in for ChatOpenAI: with_structured_output returns a canned include_raw result."""

    def __init__(self, result):
        self.result = result

    def with_structured_output(self, schema, **kwargs):
        assert kwargs == {"method": "json_schema", "strict": True, "include_raw": True}
        return RunnableLambda(lambda _: self.result)


def _llm_with(result) -> OpenAILLM:
    llm = OpenAILLM(Settings())
    llm._client = lambda stage: _FakeChat(result)
    return llm


RAW = AIMessage(
    content="",
    usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    response_metadata={"model_name": "gpt-5.4-mini-2026-03-01"},
)


def test_openai_wrapper_returns_parsed_output_and_usage():
    reply = _llm_with({"raw": RAW, "parsed": Draft(subject="s", body="b"), "parsing_error": None}).generate(
        "Writing", Draft, "sys", "user"
    )
    assert reply.parsed.subject == "s"
    assert reply.usage.input_tokens == 10 and reply.model == "gpt-5.4-mini-2026-03-01"


def test_openai_wrapper_raises_on_parse_error_but_keeps_usage():
    llm = _llm_with({"raw": RAW, "parsed": None, "parsing_error": ValueError("bad json")})
    with pytest.raises(LLMError, match="bad json") as caught:
        llm.generate("Writing", Draft, "sys", "user")
    assert caught.value.usage.output_tokens == 5  # the failed call was still billed


def test_reasoning_settings_reach_the_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    client = OpenAILLM(Settings())._client("Strategy")
    assert client.reasoning_effort == "medium" and client.temperature is None
