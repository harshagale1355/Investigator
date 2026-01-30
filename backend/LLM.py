from dotenv import load_dotenv
import os 
from langchain_community.chat_models import ChatOpenAI

LLM_MODEL = "openai/gpt-oss-20b:free"
LLM_BASE_URL = "https://openrouter.ai/api/v1"

load_dotenv()
TEMPERATURE = 0.2

def llm_model():
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=TEMPERATURE,
    )
 

