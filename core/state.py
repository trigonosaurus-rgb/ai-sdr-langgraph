from typing import TypedDict, Annotated
import operator

class SDRState(TypedDict):
    # Input data
    company_url: str
    company_name: str
    
    # Collected information (Researcher)
    company_info: str
    search_queries: list[str]
    research_iterations: int
    is_valid_company: bool
    
    # Sales strategy (Strategist)
    strategy: str
    
    # Email draft (Copywriter)
    email_draft: str
    is_spam: bool
    spam_feedback: str
    copywriter_iterations: int
    
    # Message log (optional for LangGraph)
    messages: Annotated[list, operator.add]
