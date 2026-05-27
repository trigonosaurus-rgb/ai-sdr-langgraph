from langchain_core.prompts import ChatPromptTemplate
from core.state import SDRState
from core.llm import get_llm
import json

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
        ("system", "You are a professional copywriter specializing in cold emails "
                   "that do not look like spam. They should be short, personalized, and hit the mark. "
                   "Do not use cliché phrases like 'hope you are doing well'. "
                   "Get straight to the point.")
    ]
    
    user_msg = f"Write an email for the company {name}. Here is the approach strategy:\n{strategy}\n\nWrite only the email text."
    
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
        ("system", "You are a strict spam filter. Read the email and determine if it looks like intrusive spam or a generic mass mailing. "
                   "Return a JSON strictly with two keys: "
                   "'is_spam' (true/false) and 'feedback' (a string with a brief explanation of why it is spam, or an empty string if it's fine)."),
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
        # Default to not spam if parsing fails
        is_spam = False
        feedback = ""
        
    print(f"[Spam Checker] Is email spam? -> {is_spam}. Feedback: {feedback}")
    
    return {
        "is_spam": is_spam,
        "spam_feedback": feedback
    }
