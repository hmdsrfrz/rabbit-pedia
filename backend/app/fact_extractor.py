import os
from typing import Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_GROQ_API_KEY = os.getenv("GROQ_CLIENT_ID")


class ExtractedFacts(BaseModel):
    profession: Optional[str] = Field(default=None, description="User's job, role, or field of study if explicitly stated")
    interests: Optional[str] = Field(default=None, description="Hobbies or domains the user explicitly says they're interested in")
    location: Optional[str] = Field(default=None, description="Where the user lives or is from, if stated")
    expertise_level: Optional[str] = Field(default=None, description="Beginner / intermediate / expert if implied or stated")
    other: Optional[str] = Field(default=None, description="Any other notable self-stated personal fact")


_SYSTEM = """Extract self-stated personal facts from the user's message.
Only fill a field if the user EXPLICITLY says it about themselves (e.g. "I'm a...", "I study...", "I live in...").
Never infer. Never guess. If nothing is self-stated, leave every field null."""


class FactExtractor:
    def __init__(self):
        llm = ChatGroq(
            api_key=_GROQ_API_KEY,
            model="llama-3.1-8b-instant",
            max_tokens=200,
        )
        self._llm = llm.with_structured_output(ExtractedFacts)

    async def extract(self, message: str) -> dict[str, str]:
        try:
            result: ExtractedFacts = await self._llm.ainvoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=message),
            ])
            return {k: v for k, v in result.model_dump().items() if v}
        except Exception:
            return {}
