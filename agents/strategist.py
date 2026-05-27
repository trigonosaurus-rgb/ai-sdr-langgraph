from langchain_core.prompts import ChatPromptTemplate
from core.state import SDRState
from core.llm import get_llm
import traceback

def strategist_node(state: SDRState):
    """
    Strategist Agent: analyzes information and devises a sales strategy.
    """
    company_info = state.get("company_info", "")
    name = state.get("company_name", "")
    
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a brilliant B2B sales strategist. "
                   "Your task is to analyze company data and come up with "
                   "the best approach to pitch to them, highlighting the value we can offer. "
                   "Formulate 2-3 key 'pain points' for this company and how to start a conversation with them."),
        ("user", "Company information for {company_name}:\n{company_info}\n\nWrite a strategy for cold outreach.")
    ])
    
    try:
        chain = prompt | llm
        result = chain.invoke({"company_name": name, "company_info": company_info})
        strategy_content = result.content
        print(f"[Strategist] Strategy formulated successfully.")
    except Exception as e:
        print(f"[Strategist] LLM error: {e}")
        traceback.print_exc()
        strategy_content = f"Error generating strategy: {e}"
    
    return {
        "strategy": strategy_content
    }
