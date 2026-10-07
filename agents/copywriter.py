"""Copywriter: writes the draft; on a rewrite it sees the previous draft and the review issues.
The draft is streamed to the client as it is generated."""

from typing import Any, Literal

from agents.common import TONE_GUIDES, format_facts
from agents.strategist import format_strategy
from core.context import RunContext
from core.events import DraftDelta, DraftReset, StageStarted, emit
from core.prompts import load_prompt
from core.schemas import Attempt, Draft
from core.state import SDRState


class EmptyDraftError(ValueError):
    pass


Field = Literal["subject", "body"]
FIELDS: tuple[Field, ...] = ("subject", "body")


class DraftStream:
    """Turns partial drafts into draft_delta events whose concatenation equals the final draft.

    Whitespace at either end is held back, since the final draft is stripped; a partial value that is
    not an extension of what was sent is skipped, and finish() repairs any remaining mismatch."""

    def __init__(self, attempt: int):
        self.attempt = attempt
        self.sent: dict[Field, str] = {field: "" for field in FIELDS}

    def _send(self, field: Field, text: str) -> None:
        if len(text) > len(self.sent[field]) and text.startswith(self.sent[field]):
            emit(DraftDelta(field=field, delta=text[len(self.sent[field]) :]))
            self.sent[field] = text

    def update(self, partial: dict[str, Any]) -> None:
        for field in FIELDS:
            if isinstance(value := partial.get(field), str):
                self._send(field, value.strip())

    def finish(self, draft: Draft) -> None:
        final: dict[Field, str] = {"subject": draft.subject, "body": draft.body}
        if any(not final[field].startswith(self.sent[field]) for field in FIELDS):
            emit(DraftReset(attempt=self.attempt))
            self.sent = {field: "" for field in FIELDS}
        for field in FIELDS:
            self._send(field, final[field])


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
        emit(DraftReset(attempt=number))  # a rewrite replaces the previous draft from its first token
        stream = DraftStream(number)
        draft = ctx.ask("Writing", number, prompt, Draft, system, user, on_partial=stream.update)
        draft = Draft(subject=draft.subject.strip(), body=draft.body.strip())
        if not draft.subject or not draft.body:
            raise EmptyDraftError("model returned an empty subject or body")
        stream.finish(draft)
        return {
            "attempts": [*attempts, Attempt(attempt=number, draft=draft)],
            "prompt_versions": {prompt.name: prompt.tag},
        }

    return copywriter
