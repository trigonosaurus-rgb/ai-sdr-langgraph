"""Model configurations compared in the evaluation. Each maps every stage to a model and effort."""

from core.config import StageModel, stage_models
from core.schemas import Stage

ModelConfig = dict[Stage, StageModel]

CONFIGS: dict[str, ModelConfig] = {
    "mini": stage_models("gpt-5.4-mini"),  # the current baseline
    "luna": stage_models("gpt-6-luna"),
    "sol": stage_models("gpt-6.1-sol"),
}


def describe(config: ModelConfig) -> str:
    return ", ".join(f"{stage} {m.model}/{m.reasoning_effort or 'default'}" for stage, m in config.items())
