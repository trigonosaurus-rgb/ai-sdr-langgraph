"""Review: checks language, tone, grounding and spamminess of the current draft."""

from agents.common import TONE_GUIDES, format_facts
from core.context import RunContext
from core.events import Reviewed, StageStarted, emit
from core.prompts import load_prompt
from core.schemas import Review
from core.state import SDRState

NO_REASON = "The reviewer rejected the draft without naming a problem."


def make_reviewer(ctx: RunContext):
    prompt = load_prompt("review")

    def reviewer(state: SDRState) -> dict:
        brief = state["brief"]
        attempts = state["attempts"]
        current = attempts[-1]
        emit(StageStarted(stage="Review", message=f"Checking draft {current.attempt}"))
        review = ctx.ask(
            "Review",
            current.attempt,
            prompt,
            Review,
            prompt.render("system", language=brief.language, tone_guide=TONE_GUIDES[brief.tone]),
            prompt.render(
                "user",
                company=brief.company,
                recipient=brief.recipient,
                offer=brief.offer,
                facts=format_facts(state["research"].facts),
                subject=current.draft.subject,
                body=current.draft.body,
            ),
        )
        if not review.passed and not review.issues:
            review = Review(passed=False, issues=[NO_REASON])
        emit(Reviewed(attempt=current.attempt, passed=review.passed, issues=review.issues))
        reviewed = current.model_copy(update={"review": review})
        return {
            "attempts": [*attempts[:-1], reviewed],
            "prompt_versions": {prompt.name: prompt.tag},
        }

    return reviewer
