"""Strategy: one grounded observation, the link to the offer, explicit hypotheses."""

from agents.common import format_facts
from core.context import RunContext
from core.events import StageStarted, StrategyReady, StrategyView, emit
from core.prompts import load_prompt
from core.schemas import Strategy
from core.state import SDRState


def make_strategist(ctx: RunContext):
    prompt = load_prompt("strategy")

    def strategist(state: SDRState) -> dict:
        brief, facts = state["brief"], state["research"].facts
        emit(StageStarted(stage="Strategy", message=f"Choosing an angle for the {brief.recipient}"))
        strategy = ctx.ask(
            "Strategy",
            1,
            prompt,
            Strategy,
            prompt.render("system"),
            prompt.render(
                "user",
                company=brief.company,
                domain=brief.domain,
                recipient=brief.recipient,
                offer=brief.offer,
                facts=format_facts(facts),
            ),
        )
        known = {fact.id for fact in facts}
        strategy = strategy.model_copy(
            update={"fact_ids": [i for i in strategy.fact_ids if i in known]}
        )
        emit(StrategyReady(strategy=StrategyView(**strategy.model_dump())))
        return {"strategy": strategy, "prompt_versions": {prompt.name: prompt.tag}}

    return strategist


def format_strategy(strategy: Strategy) -> str:
    hypotheses = "\n".join(f"- {h}" for h in strategy.hypotheses) or "- none"
    return (
        f"Observation: {strategy.observation}\n"
        f"Link to the offer: {strategy.offer_link}\n"
        f"Opening angle: {strategy.angle}\n"
        f"Hypotheses (unconfirmed, do not state as facts):\n{hypotheses}"
    )
