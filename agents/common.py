"""Formatting shared by the prompts of several nodes."""

from core.schemas import Fact, Language, Tone

TONE_GUIDES: dict[Tone, str] = {
    "Direct": "direct and matter-of-fact: short sentences, the point in the first line, no small talk.",
    "Warm": "warm and personable: friendly and human, a little more context, still concise and never gushing.",
}


# Language-specific rules for the copywriter; the Russian ones target errors seen in evaluation.
LANGUAGE_GUIDES: dict[Language, str] = {
    "English": "Use plain, everyday English.",
    "Russian": (
        "Decline the company name like an ordinary noun when it stands without quotes: у Контура, в Контуре, "
        "для ВкусВилла. Names in Latin script stay as written. If a form sounds odd, write «компания „Контур“». "
        "Use Russian words, not English jargon such as CTA, roadmaps, speaking practice or support-команда; "
        "only brand and product names stay in Latin script."
    ),
}

def format_facts(facts: list[Fact]) -> str:
    return "\n".join(f"[{fact.id}] {fact.claim} (source: {fact.source_title})" for fact in facts)
