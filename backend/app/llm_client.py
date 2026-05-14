import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_GROQ_API_KEY = os.getenv("GROQ_CLIENT_ID")


def get_llm(
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.7,
    max_tokens: int = 4000,
) -> ChatGroq:
    return ChatGroq(
        api_key=_GROQ_API_KEY,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
