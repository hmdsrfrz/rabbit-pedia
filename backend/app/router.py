import os
from typing import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_GROQ_API_KEY = os.getenv("GROQ_CLIENT_ID")


class RouteDecision(BaseModel):
    intent: Literal["research", "conversational"] = Field(
        description=(
            "research = the user is asking about a new topic, person, place, concept, event, etc. "
            "(any factual lookup that benefits from a Wikipedia article). "
            "conversational = the user is reacting, chatting, asking a follow-up opinion, "
            "or replying to RabbitPedia's Two Cents without naming a new topic."
        )
    )


_SYSTEM = """You classify a user's message into one of two intents for RabbitPedia, a Wikipedia chatbot.

- research: any message that names a topic worth looking up on Wikipedia (e.g. "tell me about neutron stars", "who was Ada Lovelace", "the French Revolution", or even just "neutron stars").
- conversational: short reactions, opinions, follow-up chatter, or clarifying questions about what was just said (e.g. "that's wild", "really?", "why do you think so?", "haha nice").

When in doubt, prefer research."""


class IntentRouter:
    def __init__(self):
        llm = ChatGroq(
            api_key=_GROQ_API_KEY,
            model="llama-3.1-8b-instant",
            max_tokens=50,
        )
        self._llm = llm.with_structured_output(RouteDecision)

    async def classify(self, message: str, has_history: bool) -> str:
        if not has_history:
            return "research"
        try:
            result: RouteDecision = await self._llm.ainvoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=message),
            ])
            return result.intent
        except Exception:
            return "research"


_CHAT_SYSTEM = """You are RabbitPedia. The user is chatting with you about something you just covered.
Reply naturally and conversationally — 1-3 sentences. Stay in character: curious, opinionated, knowledgeable.
Do NOT structure the reply as an article. Do NOT cite sources. Just talk."""


class ConversationalReplier:
    def __init__(self):
        self._llm = ChatGroq(
            api_key=_GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            max_tokens=300,
        )

    async def reply(self, message: str, history: list[dict], user_facts: dict[str, str]) -> str:
        msgs = [SystemMessage(content=_CHAT_SYSTEM)]
        if user_facts:
            facts_str = "; ".join(f"{k}: {v}" for k, v in list(user_facts.items())[:8])
            msgs.append(SystemMessage(content=f"About the user: {facts_str}"))
        recent = history[-10:] if history else []
        convo = []
        for m in recent:
            role = m.get("role", "")
            content = m.get("content", "")[:300]
            convo.append(f"{role}: {content}")
        if convo:
            msgs.append(SystemMessage(content="Recent conversation:\n" + "\n".join(convo)))
        msgs.append(HumanMessage(content=message))
        result = await self._llm.ainvoke(msgs)
        return result.content if hasattr(result, "content") else str(result)
