from langchain_core.prompts import ChatPromptTemplate
from core.state import SDRState
from core.llm import get_llm
import json
import traceback

def copywriter_node(state: SDRState):
    """
    Copywriter Agent: writes a cold email based on the strategy.
    """
    strategy = state.get("strategy", "")
    name = state.get("company_name", "")
    iterations = state.get("copywriter_iterations", 0)
    feedback = state.get("spam_feedback", "")
    
    llm = get_llm()
    
    messages = [
        ("system", "You are an expert B2B copywriter specializing in ultra-concise, highly personalized cold emails. "
                   "Your emails should feel like they were written manually by a peer, not a marketer. "
                   "Rules: "
                   "1. Keep it under 50 words. "
                   "2. Do NOT use marketing jargon, buzzwords, or cliché greetings like 'hope you are doing well'. "
                   "3. Use the provided strategy to mention a SPECIFIC pain point or observation about their business, and briefly propose a solution. "
                   "4. Ask a single, relevant question at the end related to that specific pain point. "
                   "5. Make it sound highly conversational and plain-text.")
    ]
    
    user_msg = f"Write an email for the company {name}. Here is the approach strategy (based on our research):\n{strategy}\n\nMake sure to explicitly mention their specific business context or pain point from the strategy. Output ONLY the email text, no subject line, no pleasantries."
    
    # If this is not the first attempt, include feedback from the Spam Checker
    if iterations > 0 and feedback:
        user_msg += f"\n\nIMPORTANT: Your previous version was rejected by the spam filter. Here is the feedback from the reviewer:\n{feedback}\n\nPlease rewrite the email taking these comments into account, making it more human and less promotional."
        
    messages.append(("user", user_msg))
    
    prompt = ChatPromptTemplate.from_messages(messages)
    
    try:
        chain = prompt | llm
        result = chain.invoke({})
        email_content = result.content
        print(f"[Copywriter] Email written (attempt {iterations + 1}).")
    except Exception as e:
        print(f"[Copywriter] LLM error: {e}")
        traceback.print_exc()
        email_content = f"Error generating email: {e}"
    
    return {
        "email_draft": email_content,
        "copywriter_iterations": iterations + 1
    }

def spam_checker_node(state: SDRState):
    """
    Node that checks the email for spam characteristics.
    """
    email = state.get("email_draft", "")
    iterations = state.get("copywriter_iterations", 0)
    llm = get_llm()
    
    # Limit the number of attempts to avoid infinite loops
    if iterations >= 3:
        print("[Spam Checker] Attempt limit exceeded. Skipping email as is.")
        return {"is_spam": False, "spam_feedback": "Attempt limit reached."}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert B2B sales coach reviewing a cold email. "
                   "Your goal is to detect emails that sound 'salesy', overly promotional, generic, or use marketing buzzwords. "
                   "Acknowledge that this IS a cold email, so being unsolicited is fine, but it MUST sound like a human-to-human message. "
                   "Return a JSON strictly with two keys: "
                   "'is_spam' (true if it sounds like an automated/promotional blast, false if it reads like a natural, thoughtful note) "
                   "and 'feedback' (brief explanation of what to fix, or empty if false)."),
        ("user", "Email:\n{email}")
    ])
    
    try:
        chain = prompt | llm
        result = chain.invoke({"email": email})
        
        # Attempt to parse JSON
        text = result.content.strip().replace("```json", "").replace("```", "")
        data = json.loads(text)
        is_spam = data.get("is_spam", False)
        feedback = data.get("feedback", "")
    except Exception as e:
        print(f"[Spam Checker] Parsing error: {e}")
        traceback.print_exc()
        # Default to not spam if parsing fails
        is_spam = False
        feedback = ""
        
    print(f"[Spam Checker] Is email spam? -> {is_spam}. Feedback: {feedback}")
    
    return {
        "is_spam": is_spam,
        "spam_feedback": feedback
    }
