"""Copywriter: writes the draft; on a rewrite it sees the previous draft and the review issues."""

from agents.common import TONE_GUIDES, format_facts
from agents.strategist import format_strategy
from core.context import RunContext
from core.events import DraftDelta, DraftReset, StageStarted, emit
from core.prompts import load_prompt
from core.schemas import Attempt, Draft
from core.state import SDRState


class EmptyDraftError(ValueError):
    pass


def make_copywriter(ctx: RunContext):
    prompt = load_prompt("copywriter")

    def copywriter(state: SDRState) -> dict:
        brief = state["brief"]
        attempts = state.get("attempts", [])
        number = len(attempts) + 1
        message = "Writing the first draft" if number == 1 else f"Rewriting the draft, attempt {number}"
        emit(StageStarted(stage="Writing", message=message))

        user = prompt.render(
            "user",
            company=brief.company,
            recipient=brief.recipient,
            offer=brief.offer,
            facts=format_facts(state["research"].facts),
            strategy=format_strategy(state["strategy"]),
        )
        if attempts:
            previous = attempts[-1]
            issues = previous.review.issues if previous.review else []
            user += "\n\n" + prompt.render(
                "revision",
                previous_subject=previous.draft.subject,
                previous_body=previous.draft.body,
                issues="\n".join(f"- {issue}" for issue in issues),
            )
        system = prompt.render("system", language=brief.language, tone_guide=TONE_GUIDES[brief.tone])
        draft = ctx.ask("Writing", number, prompt, Draft, system, user)
        draft = Draft(subject=draft.subject.strip(), body=draft.body.strip())
        if not draft.subject or not draft.body:
            raise EmptyDraftError("model returned an empty subject or body")

        emit(DraftReset(attempt=number))
        emit(DraftDelta(field="subject", delta=draft.subject))
        emit(DraftDelta(field="body", delta=draft.body))
        return {
            "attempts": [*attempts, Attempt(attempt=number, draft=draft)],
            "prompt_versions": {prompt.name: prompt.tag},
        }

    return copywriter
