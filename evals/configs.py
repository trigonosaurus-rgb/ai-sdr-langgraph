"""Model configurations compared in the evaluation. Each maps every stage to a model and effort."""

from core.config import StageModel, stage_models
from core.schemas import Stage

ModelConfig = dict[Stage, StageModel]

CONFIGS: dict[str, ModelConfig] = {
    "mini": stage_models("gpt-5.4-mini"),  # the current baseline
    "luna": stage_models("gpt-6-luna"),
    "sol": stage_models("gpt-6.1-sol"),
    # Chosen from the v2 comparison: luna extracts facts as reliably at a tenth of the cost, sol picks
    # the most relevant angles, mini writes the most natural drafts and reviews without nitpicking.
    "mix": {
        "Research": StageModel("gpt-6-luna", reasoning_effort="low"),
        "Strategy": StageModel("gpt-6.1-sol", reasoning_effort="medium"),
        "Writing": StageModel("gpt-5.4-mini", reasoning_effort="medium"),
        "Review": StageModel("gpt-5.4-mini", reasoning_effort="low"),
    },
}


def describe(config: ModelConfig) -> str:
    return ", ".join(f"{stage} {m.model}/{m.reasoning_effort or 'default'}" for stage, m in config.items())
