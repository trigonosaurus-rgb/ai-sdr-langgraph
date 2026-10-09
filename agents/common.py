"""Formatting shared by the prompts of several nodes."""

from core.schemas import Fact, Tone

TONE_GUIDES: dict[Tone, str] = {
    "Direct": "direct and matter-of-fact: short sentences, the point in the first line, no small talk.",
    "Warm": "warm and personable: friendly and human, a little more context, still concise and never gushing.",
}


def format_facts(facts: list[Fact]) -> str:
    return "\n".join(f"[{fact.id}] {fact.claim} (source: {fact.source_title})" for fact in facts)
