import os
from typing import Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from app.wikipedia_fetcher import Article

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_GROQ_API_KEY = os.getenv("GROQ_CLIENT_ID")


class KeyConcept(BaseModel):
    term: str
    definition: str


class Source(BaseModel):
    title: str
    url: str = Field(description="Must be an exact URL from the provided Wikipedia context. Never fabricate.")


class ExploreFurther(BaseModel):
    from_article: list[str] = Field(description="Topics from the article's See Also list")
    you_might_like: list[str] = Field(
        description=(
            "4-6 suggestions to take the user deeper. MUST mix two formats: "
            "(a) 2-3 short topic names like 'Quantum entanglement' or 'French Revolution'; "
            "AND (b) 2-3 specific full-sentence questions ending with '?' that invite curiosity, "
            "e.g. 'How did garage rock revival reshape indie music in the 2000s?' or "
            "'What caused the collapse of the Roman Republic?'. "
            "The questions must be specific to the current topic, intriguing, and unique — not generic."
        )
    )


class ResponseSection(BaseModel):
    heading: str = Field(description="The topic title")
    body: str = Field(
        description=(
            "Multi-paragraph synthesis of the topic. Separate each paragraph with a literal '\\n\\n' "
            "(double newline). Default: 2-4 paragraphs. In DEEP MODE: 4-5 paragraphs, each on a "
            "distinct facet (history, mechanism, impact, controversy, etc)."
        )
    )
    key_concepts: Optional[list[KeyConcept]] = Field(
        default=None,
        description="3-5 key terms and definitions. Omit entirely (null) if not applicable."
    )
    did_you_know: list[str] = Field(description="2-3 interesting facts about the topic")
    two_cents: str = Field(description="1-2 paragraphs of opinionated commentary on what makes this topic fascinating")
    sources: list[Source] = Field(description="Wikipedia sources. URLs must come verbatim from the provided context.")
    explore_further: ExploreFurther


_SYSTEM_PROMPT = """\
You are RabbitPedia, a Wikipedia-powered research assistant.
Synthesize the provided Wikipedia article into a structured response.

CRITICAL URL RULES:
- The `sources` field must only contain the exact URL(s) provided in the context.
- Never invent, guess, or fabricate any Wikipedia URLs.
- ALWAYS include at least one source entry whenever an article URL is provided in the context — every response must let the user click through to the Wikipedia article you drew from.
- Only return an empty sources list if NO article URL was provided.
"""


def _format_personalization(interests: list[str], user_facts: dict[str, str]) -> str:
    parts = []
    if interests:
        parts.append("User has shown interest in: " + ", ".join(interests[:5]))
        parts.append("Bias `explore_further.you_might_like` toward these themes when relevant.")
    if user_facts:
        facts_str = "; ".join(f"{k}: {v}" for k, v in list(user_facts.items())[:8])
        parts.append(f"Known about user (use to tailor tone/examples, do not repeat back verbatim): {facts_str}")
    if not parts:
        return ""
    return "\n\n" + "\n".join(parts)


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    pairs = []
    for i in range(0, len(history) - 1, 2):
        if i + 1 < len(history):
            user_content = history[i]["content"][:150]
            ai_content = history[i + 1]["content"][:250]
            pairs.append(f'User asked: "{user_content}"\nYou covered: {ai_content}')
    if not pairs:
        return ""
    recent = pairs[-5:]
    return (
        "\n\nPRIOR CONVERSATION (the user is continuing this thread — refer back when relevant, "
        "use it to disambiguate pronouns and follow-ups, do NOT re-explain things you've already covered):\n"
        + "\n---\n".join(recent)
    )


class ResponseFormatter:
    def __init__(self):
        llm = ChatGroq(
            api_key=_GROQ_API_KEY,
            model="llama-3.3-70b-versatile",
            max_tokens=3000,
        )
        self._structured_llm = llm.with_structured_output(ResponseSection)

    def _build_messages(
        self,
        query: str,
        articles: list[Article],
        history: list[dict] | None = None,
        interests: list[str] | None = None,
        user_facts: dict[str, str] | None = None,
    ) -> list:
        primary = articles[0]
        see_also_str = ", ".join(primary["see_also"][:8]) if primary["see_also"] else "None"

        article_blocks = []
        for i, art in enumerate(articles):
            url_str = art["url"] if art["url"] else "(no URL available — do not cite)"
            article_blocks.append(
                f"""Article {i + 1}:
Title: {art["title"] or "(none)"}
URL (use this exactly in sources if cited): {url_str}
Summary: {art["summary"][:2200] or "(no content)"}"""
            )
        articles_str = "\n\n".join(article_blocks)

        depth_hint = ""
        if len(articles) > 1:
            depth_hint = (
                "\n\nDEEP MODE — your response MUST be visibly richer than a shallow response:"
                "\n- Body MUST be 4-5 paragraphs, each covering a distinct facet of the topic (history, mechanism, impact, controversy, etc)."
                "\n- key_concepts MUST be populated with at least 4 entries — do NOT leave it null in deep mode."
                "\n- did_you_know should have 3 facts, drawing from across the articles."
                "\n- Cite every article URL you used in sources (one Source entry per article)."
                "\n- Weave distinct insights from each article — do not just repeat the primary article's summary."
            )

        context = f"""Wikipedia source material:
{articles_str}

See Also (use for explore_further.from_article): {see_also_str}{depth_hint}"""

        system_content = (
            _SYSTEM_PROMPT
            + _format_personalization(interests or [], user_facts or {})
            + _format_history(history or [])
        )

        return [
            SystemMessage(content=system_content),
            SystemMessage(content=context),
            HumanMessage(content=f"Write a RabbitPedia article about: {query}"),
        ]

    async def format(
        self,
        query: str,
        article: Article | list[Article],
        history: list[dict] | None = None,
        interests: list[str] | None = None,
        user_facts: dict[str, str] | None = None,
    ) -> ResponseSection:
        articles = article if isinstance(article, list) else [article]
        messages = self._build_messages(query, articles, history, interests, user_facts)
        result = await self._structured_llm.ainvoke(messages)
        return result
