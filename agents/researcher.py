import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.tavily_search import TavilySearchResults
from core.state import SDRState
from core.llm import get_llm

def researcher_node(state: SDRState):
    """
    Researcher Agent: searches the internet for company information.
    """
    url = state.get("company_url", "")
    name = state.get("company_name", "")
    iterations = state.get("research_iterations", 0)
    
    llm = get_llm()
    # Tavily search tool (requires TAVILY_API_KEY in .env)
    search = TavilySearchResults(max_results=3)
    
    # Formulate search query
    query = f"what does the company {name} ({url}) do? What are their main products and target audience?"
    if iterations > 0:
        query = f"recent news and challenges for company {name} {url}"
        
    print(f"[Researcher] Executing search: {query}")
    
    # Perform internet search with fault tolerance
    try:
        search_results = search.invoke({"query": query})
        if isinstance(search_results, list):
            content = "\n".join([res.get("content", "") for res in search_results if isinstance(res, dict)])
        else:
            content = str(search_results)
    except Exception as e:
        print(f"[Researcher] Search error: {e}")
        content = f"Search error occurred: {e}"
        
    # Ask LLM to summarize the findings
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an experienced research analyst. Your task is to review the information found on the internet about a company and create a concise but comprehensive report: what the company does, what products it sells, and who its target audience is."),
        ("user", "Here is the raw data from the internet about the company {company_name} ({company_url}):\n\n{content}\n\nProvide a summary.")
    ])
    
    try:
        chain = prompt | llm
        summary = chain.invoke({"company_name": name, "company_url": url, "content": content})
        summary_content = summary.content
    except Exception as e:
        print(f"[Researcher] LLM error: {e}")
        summary_content = f"Error generating summary: {e}"
    
    # Update the state
    return {
        "company_info": summary_content,
        "research_iterations": iterations + 1,
        "search_queries": state.get("search_queries", []) + [query]
    }
