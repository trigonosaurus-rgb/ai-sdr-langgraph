"""researcher -> strategist -> copywriter <-> reviewer, with an early exit after research."""

from langgraph.graph import END, START, StateGraph

from agents.copywriter import make_copywriter
from agents.researcher import make_researcher
from agents.reviewer import make_reviewer
from agents.strategist import make_strategist
from core.context import RunContext
from core.state import SDRState


def route_after_research(state: SDRState) -> str:
    return END if state.get("stop") else "strategist"


def make_review_router(max_attempts: int):
    def route_after_review(state: SDRState) -> str:
        current = state["attempts"][-1]
        if current.review and current.review.passed:
            return END
        return "copywriter" if current.attempt < max_attempts else END

    return route_after_review


def build_graph(ctx: RunContext):
    builder = StateGraph(SDRState)
    builder.add_node("researcher", make_researcher(ctx))
    builder.add_node("strategist", make_strategist(ctx))
    builder.add_node("copywriter", make_copywriter(ctx))
    builder.add_node("reviewer", make_reviewer(ctx))

    builder.add_edge(START, "researcher")
    builder.add_conditional_edges("researcher", route_after_research, ["strategist", END])
    builder.add_edge("strategist", "copywriter")
    builder.add_edge("copywriter", "reviewer")
    builder.add_conditional_edges(
        "reviewer",
        make_review_router(1 + ctx.settings.max_rewrites),
        ["copywriter", END],
    )
    return builder.compile()
