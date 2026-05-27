import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm():
    # Retrieve the model name from .env, using gpt-5.4-mini as the default
    model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-5.4-mini")
    # ChatOpenAI automatically loads OPENAI_API_KEY from the environment
    # Setting temperature to 0.5 to balance accuracy (for analysis) and creativity (for copywriting)
    return ChatOpenAI(model=model_name, temperature=0.5)
