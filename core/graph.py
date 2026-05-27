from langgraph.graph import StateGraph, START, END
from core.state import SDRState
from agents.researcher import researcher_node
from agents.strategist import strategist_node
from agents.copywriter import copywriter_node, spam_checker_node

# Routing function: determines the next step after the spam check
def route_after_spam_check(state: SDRState) -> str:
    """
    Reads the state and checks the is_spam flag.
    If True, returns "copywriter" to rewrite the email.
    If False, returns "END" to finish the workflow.
    """
    if state.get("is_spam", False):
        print("[Router] Email looks like spam. Routing back to copywriter.")
        return "copywriter"
    print("[Router] Email passed spam check. Terminating workflow.")
    return END

# Initialize the state graph with the SDRState structure
builder = StateGraph(SDRState)

# 1. Add nodes
# The first argument is the node name, the second is the agent function
builder.add_node("researcher", researcher_node)
builder.add_node("strategist", strategist_node)
builder.add_node("copywriter", copywriter_node)
builder.add_node("spam_checker", spam_checker_node)

# 2. Define standard edges (strict sequence)
# START always leads to the Researcher
builder.add_edge(START, "researcher")
# Researcher passes data to the Strategist
builder.add_edge("researcher", "strategist")
# Strategist passes strategy to the Copywriter
builder.add_edge("strategist", "copywriter")
# Copywriter always proceeds to the Spam Checker
builder.add_edge("copywriter", "spam_checker")

# 3. Define conditional edges (for loops)
# After spam_checker, call route_after_spam_check
# to decide whether to return to "copywriter" or end the workflow
builder.add_conditional_edges(
    "spam_checker", 
    route_after_spam_check,
    {
        "copywriter": "copywriter",
        END: END
    }
)

# Compile the graph into an executable application
app = builder.compile()
