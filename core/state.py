from typing import Annotated, TypedDict

from core.schemas import Attempt, Brief, FailureReason, Research, Strategy


def merge(left: dict, right: dict) -> dict:
    return {**left, **right}


class SDRState(TypedDict, total=False):
    brief: Brief
    research: Research
    # Set by research when the run cannot continue honestly.
    stop: FailureReason
    strategy: Strategy
    # Drafts in order; the last one is current. Nodes return the whole list.
    attempts: list[Attempt]
    # Prompt name -> version used in this run.
    prompt_versions: Annotated[dict[str, str], merge]
