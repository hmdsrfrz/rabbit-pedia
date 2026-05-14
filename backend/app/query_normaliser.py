import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_GROQ_API_KEY = os.getenv("GROQ_CLIENT_ID")

_SYSTEM = """You convert a user's question into the best Wikipedia article title to look up.

Rules:
- Output ONLY the article title — no quotes, no punctuation, no explanation.
- Strip question phrasing ("how many", "what is", "who was", etc.).
- Use the canonical article name when obvious (e.g. "Fall of the Western Roman Empire", not "why rome fell").
- If the input is already a clean topic name, return it unchanged.
- Keep it short: 1-6 words.

Examples:
"how many books are in the harry potter series" -> Harry Potter
"why did rome fall" -> Fall of the Western Roman Empire
"tell me about quantum entanglement" -> Quantum entanglement
"The Strokes" -> The Strokes
"who was ada lovelace" -> Ada Lovelace
"""


class QueryNormaliser:
    def __init__(self):
        self._llm = ChatGroq(
            api_key=_GROQ_API_KEY,
            model="llama-3.1-8b-instant",
            max_tokens=30,
        )

    async def normalize(self, message: str) -> str:
        msg = (message or "").strip()
        if not msg:
            return ""
        try:
            result = await self._llm.ainvoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=msg),
            ])
            text = result.content if hasattr(result, "content") else str(result)
            cleaned = text.strip().strip('"\'').splitlines()[0].strip()
            return cleaned or msg
        except Exception:
            return msg
