"""Run configuration: models per stage, limits and search settings."""

import os
from dataclasses import dataclass, field, replace
from typing import Literal

from core.schemas import Stage

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
DEFAULT_MODEL = "gpt-5.4-mini"


@dataclass(frozen=True)
class StageModel:
    model: str = DEFAULT_MODEL
    reasoning_effort: ReasoningEffort | None = None  # None: provider default
    temperature: float | None = None  # None: not sent; reasoning models reject it


def stage_models(model: str) -> dict[Stage, StageModel]:
    """One model for every stage, with the reasoning effort each stage needs."""
    return {
        "Research": StageModel(model, reasoning_effort="low"),
        "Strategy": StageModel(model, reasoning_effort="medium"),
        "Writing": StageModel(model, reasoning_effort="medium"),
        "Review": StageModel(model, reasoning_effort="low"),
    }


@dataclass(frozen=True)
class Settings:
    models: dict[Stage, StageModel] = field(default_factory=lambda: stage_models(DEFAULT_MODEL))
    max_rewrites: int = 2  # drafts after the first one; total attempts = 1 + max_rewrites
    min_facts: int = 2  # fewer verified facts than this means insufficient data
    search_results_per_query: int = 5
    source_chars: int = 1500  # search result content passed to the LLM, per result
    llm_timeout_s: float = 90
    llm_max_retries: int = 2

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(models=stage_models(os.getenv("OPENAI_MODEL_NAME") or DEFAULT_MODEL))
        if value := os.getenv("SDR_MAX_REWRITES"):
            settings = replace(settings, max_rewrites=int(value))
        return settings
