import os
from typing import AsyncGenerator, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_GROQ_API_KEY = os.getenv("GROQ_CLIENT_ID")

_SYSTEM_PROMPT = """You are RabbitPedia, a Wikipedia-powered research assistant.
You synthesize Wikipedia content into clear, informative responses.
Keep responses concise and accurate. Use the provided article content when available."""


class ResearchAgent:
    def __init__(self):
        self._llm = ChatGroq(
            api_key=_GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            max_tokens=1024,
            streaming=True,
        )

    async def run(
        self,
        query: str,
        article: Optional[dict] = None,
        history: list = [],
    ) -> AsyncGenerator[str, None]:
        messages = [SystemMessage(content=_SYSTEM_PROMPT)]

        if article and article.get("summary"):
            context = f"Wikipedia article: {article['title']}\n\n{article['summary'][:3000]}"
            messages.append(SystemMessage(content=context))

        messages.append(HumanMessage(content=query))

        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield chunk.content
