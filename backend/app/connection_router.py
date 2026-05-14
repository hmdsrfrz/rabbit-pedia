import asyncio
from functools import partial
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from app.wikipedia_fetcher import WikipediaFetcher
from app.llm_client import get_llm

router = APIRouter()
_fetcher = WikipediaFetcher()

_SYSTEM_PROMPT = """
You are a connection analyst for RabbitPedia.

You receive two Wikipedia articles and, where available, exact excerpts from one article that mention the other.

Rules:
- 2-3 focused paragraphs, plain prose
- Ground your explanation in the specific excerpts provided — do not invent a connection
- If excerpts are provided, name the exact event, moment, or context they describe
- Do not summarize each article separately — focus on their intersection
- Write for a curious reader who knows both topics exist but wants to understand the link
- No markdown, no bullet points
"""


def _find_mention_paragraphs(full_text: str, search_term: str, max_paras: int = 4) -> list[str]:
    """Return up to max_paras paragraphs from full_text that contain search_term (case-insensitive)."""
    term_lower = search_term.lower()
    paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]
    matches = [p for p in paragraphs if term_lower in p.lower()]
    return matches[:max_paras]


class ConnectionData(BaseModel):
    node: str
    origin: str
    heading: str
    body: str
    node_url: str
    origin_url: str


@router.get("/connection", response_model=ConnectionData)
async def get_connection(
    node: str = Query(...),
    origin: str = Query(...),
):
    loop = asyncio.get_event_loop()

    (node_article, origin_article, origin_full_text, node_full_text) = await asyncio.gather(
        loop.run_in_executor(None, partial(_fetcher.search, node)),
        loop.run_in_executor(None, partial(_fetcher.search, origin)),
        loop.run_in_executor(None, partial(_fetcher.get_full_text, origin)),
        loop.run_in_executor(None, partial(_fetcher.get_full_text, node)),
    )

    if not node_article.get("title") or not origin_article.get("title"):
        raise HTTPException(status_code=404, detail="Could not find one or both articles on Wikipedia.")

    # Find paragraphs where each article mentions the other
    node_title = node_article["title"]
    origin_title = origin_article["title"]

    mentions_in_origin = _find_mention_paragraphs(origin_full_text, node_title)
    mentions_in_node = _find_mention_paragraphs(node_full_text, origin_title)

    # Also try the short query names in case the canonical title differs
    if not mentions_in_origin:
        mentions_in_origin = _find_mention_paragraphs(origin_full_text, node)
    if not mentions_in_node:
        mentions_in_node = _find_mention_paragraphs(node_full_text, origin)

    excerpt_lines = []
    if mentions_in_origin:
        excerpt_lines.append(f'Excerpts from "{origin_title}" that mention "{node_title}":')
        for para in mentions_in_origin:
            excerpt_lines.append(f"  • {para[:400]}")
    if mentions_in_node:
        excerpt_lines.append(f'Excerpts from "{node_title}" that mention "{origin_title}":')
        for para in mentions_in_node:
            excerpt_lines.append(f"  • {para[:400]}")

    excerpt_block = "\n".join(excerpt_lines) if excerpt_lines else "(No direct cross-mention found in article body text.)"

    llm = get_llm(model="llama-3.3-70b-versatile", temperature=0.6, max_tokens=800)

    user_msg = f"""
Article 1 — {node_title}:
{node_article['summary'][:400]}

Article 2 — {origin_title}:
{origin_article['summary'][:400]}

{excerpt_block}

Explain how {node} connects to {origin}. Use the excerpts above as your primary evidence where they exist.
"""

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = await llm.ainvoke(messages)

    return ConnectionData(
        node=node,
        origin=origin,
        heading=f"{node} — {origin}",
        body=str(response.content),
        node_url=node_article.get("url", ""),
        origin_url=origin_article.get("url", ""),
    )
