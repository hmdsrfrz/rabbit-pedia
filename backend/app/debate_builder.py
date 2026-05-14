import asyncio
import json
import logging
from functools import partial
from typing import AsyncIterator, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from app.wikipedia_fetcher import WikipediaFetcher, Article
from app.llm_client import get_llm

_fetcher = WikipediaFetcher()
log = logging.getLogger("rabbitpedia.debate")

# Both use the same model for reliability of long NDJSON generation.
# The differentiation comes from the opposing system prompts, not the model version.
RED_MODEL = "llama-3.3-70b-versatile"
BLUE_MODEL = "llama-3.3-70b-versatile"


class DebateSide(BaseModel):
    id: str
    label: str
    position: str
    color: str


class DebateArgument(BaseModel):
    side_id: str
    type: str
    heading: str
    content: str
    targets: Optional[str] = None
    sources: List[str] = []


class DebateMeta(BaseModel):
    topic: str
    question: str
    context: str
    red: DebateSide
    blue: DebateSide
    verdict: str


class DebateData(BaseModel):
    topic: str
    question: str
    context: str
    red: DebateSide
    blue: DebateSide
    rounds: List[DebateArgument]
    verdict: str


_FACTUAL_GUARDRAIL = """
IMPORTANT RULES:
- Do NOT pose as an expert, academic, critic, or any professional role.
- Do NOT fabricate statistics, quotes, names, studies, or events.
- Only make factual claims that are directly supported by the provided excerpts.
- When making a logical or theoretical argument (not from the excerpts), signal it clearly: "The logic here is..." or "This suggests...".
- If you are uncertain, say so rather than inventing detail.
- You are making a case, not reporting facts. Argue forcefully but honestly.
"""

_META_SYSTEM_PROMPT = """
You are a debate architect for RabbitPedia.

Given a Wikipedia article and controversy context, produce the debate frame.
Return ONLY valid JSON with these exact fields: topic, question, context, red, blue, verdict.

question: the single most genuinely contested question (yes/no or for/against framing)
context: one neutral sentence for readers unfamiliar with the topic
red: { "id": "red", "label": "The Case For/Against...", "position": "one-line core stance", "color": "#c0392b" }
blue: { "id": "blue", "label": "The Case For/Against...", "position": "one-line core stance", "color": "#2980b9" }
verdict: what academic/expert consensus actually says — neutral, honest, no declared winner

Red is the contrarian or minority view. Blue is the mainstream or conventional view.
"""

_RED_ROUNDS_PROMPT = f"""
You are presenting the RED side of a structured debate on RabbitPedia.

Output exactly 7 rounds FOR THE RED SIDE ONLY as NEWLINE-DELIMITED JSON (NDJSON).
One complete JSON object per line. No array wrapper. No markdown fences. No extra text before or after.

Each line must be valid JSON with these exact fields:
{{
  "side_id": "red",
  "type": "opening" | "argument" | "rebuttal" | "closing",
  "heading": "short punchy heading, 4-8 words",
  "content": "2-3 assertive, specific sentences making the case",
  "targets": null or "the specific claim or position being directly contested",
  "sources": ["WikipediaTitle1"]
}}

sources: list exact article titles from the RELATED TOPICS that you drew from. Empty array otherwise.

Generate in this exact order:
1. opening     — state the core red position with conviction
2. argument    — draw from controversy excerpts; name a specific documented failure, event, or outcome
3. argument    — connect to a related topic; name it in sources
4. rebuttal    — contest the blue position directly; targets = the blue claim being attacked
5. argument    — the most technically specific point, most uncomfortable for the blue position
6. rebuttal    — dismantle blue's strongest counter-argument; targets = what is being attacked
7. closing     — make the reader feel the weight of the red case

{_FACTUAL_GUARDRAIL}
"""

_BLUE_ROUNDS_PROMPT = f"""
You are presenting the BLUE side of a structured debate on RabbitPedia.

Output exactly 7 rounds FOR THE BLUE SIDE ONLY as NEWLINE-DELIMITED JSON (NDJSON).
One complete JSON object per line. No array wrapper. No markdown fences. No extra text before or after.

Each line must be valid JSON with these exact fields:
{{
  "side_id": "blue",
  "type": "opening" | "argument" | "rebuttal" | "closing",
  "heading": "short punchy heading, 4-8 words",
  "content": "2-3 assertive, specific sentences making the case",
  "targets": null or "the specific claim or position being directly contested",
  "sources": ["WikipediaTitle1"]
}}

sources: list exact article titles from the RELATED TOPICS that you drew from. Empty array otherwise.

Generate in this exact order:
1. opening     — state the core blue position with authority
2. argument    — counter the red position using a different controversy excerpt; name the specific evidence
3. argument    — connect to a different related topic; name it in sources
4. rebuttal    — contest the red position directly; targets = the red claim being attacked
5. argument    — the most technically specific counter, most uncomfortable for the red position
6. rebuttal    — dismantle red's strongest argument; targets = what is being attacked
7. closing     — make the reader feel the weight of the blue case

{_FACTUAL_GUARDRAIL}
"""

_RED_CHALLENGE_PROMPT = f"""
You are presenting the RED side in a debate on RabbitPedia.
A viewer has issued a direct challenge. Respond from the RED position only.

Return ONLY valid JSON — a single object with these exact fields:
{{
  "side_id": "red",
  "type": "rebuttal",
  "heading": "4-8 word heading that directly answers the challenge",
  "content": "2-3 sentences addressing the challenge from the red position",
  "targets": "copy the user challenge text here exactly",
  "sources": []
}}

{_FACTUAL_GUARDRAIL}
"""

_BLUE_CHALLENGE_PROMPT = f"""
You are presenting the BLUE side in a debate on RabbitPedia.
A viewer has issued a direct challenge. Respond from the BLUE position only.

Return ONLY valid JSON — a single object with these exact fields:
{{
  "side_id": "blue",
  "type": "rebuttal",
  "heading": "4-8 word heading that directly answers the challenge",
  "content": "2-3 sentences addressing the challenge from the blue position",
  "targets": "copy the user challenge text here exactly",
  "sources": []
}}

{_FACTUAL_GUARDRAIL}
"""


async def build_research_context(article: Article) -> str:
    title = article["title"]
    loop = asyncio.get_event_loop()

    full_text, related_titles = await asyncio.gather(
        loop.run_in_executor(None, partial(_fetcher.get_full_text, title)),
        loop.run_in_executor(None, partial(_fetcher.get_links, title, 15)),
    )

    controversy_paras = _fetcher.extract_controversy_paragraphs(full_text, max_paras=12)

    async def _fetch_one(rel_title: str) -> Optional[str]:
        rel = await loop.run_in_executor(None, partial(_fetcher.search, rel_title))
        if rel.get("title") and rel.get("summary"):
            return f"- {rel['title']}: {rel['summary'][:200].rstrip()}"
        return None

    related_results = await asyncio.gather(*[_fetch_one(t) for t in related_titles[:8]])
    related_summaries = [r for r in related_results if r]

    lines: list[str] = []
    if controversy_paras:
        lines.append("=== CONTROVERSY EXCERPTS ===")
        for i, para in enumerate(controversy_paras, 1):
            lines.append(f"{i}. {para[:500]}")
    if related_summaries:
        lines.append("\n=== RELATED TOPICS ===")
        lines.extend(related_summaries)

    return "\n".join(lines)


def _parse_ndjson_stream(llm, messages, side_id: str):
    """Stream NDJSON lines from an LLM and yield DebateArguments. Handles markdown fences, trailing commas, and bare brackets."""
    async def _gen():
        buffer = ""
        async for chunk in llm.astream(messages):
            text = chunk.content if hasattr(chunk, "content") else str(chunk)
            buffer += text
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip().rstrip(",")
                if not line or line.startswith("```") or line in ("[", "]"):
                    continue
                try:
                    data = json.loads(line)
                    data["side_id"] = side_id
                    yield DebateArgument(**data)
                except Exception:
                    pass
        remaining = buffer.strip().rstrip(",")
        if remaining and not remaining.startswith("```") and remaining not in ("[", "]"):
            try:
                data = json.loads(remaining)
                data["side_id"] = side_id
                yield DebateArgument(**data)
            except Exception:
                pass
    return _gen()


class DebateBuilder:
    def __init__(self):
        meta_llm = get_llm(model=RED_MODEL, temperature=0.7, max_tokens=1000)
        self._meta_llm = meta_llm.with_structured_output(DebateMeta)

        self._red_llm = get_llm(model=RED_MODEL, temperature=0.85, max_tokens=3500)
        self._blue_llm = get_llm(model=BLUE_MODEL, temperature=0.85, max_tokens=3500)

        self._red_challenge_llm = get_llm(model=RED_MODEL, temperature=0.8, max_tokens=400).with_structured_output(DebateArgument)
        self._blue_challenge_llm = get_llm(model=BLUE_MODEL, temperature=0.8, max_tokens=400).with_structured_output(DebateArgument)

    async def build_meta(self, article: Article, research_context: str) -> DebateMeta:
        user_msg = f"""Topic: {article['title']}
Summary: {article['summary'][:600]}

{research_context[:1000]}

Produce the debate frame."""
        messages = [SystemMessage(content=_META_SYSTEM_PROMPT), HumanMessage(content=user_msg)]
        return await self._meta_llm.ainvoke(messages)

    async def stream_rounds(
        self, article: Article, research_context: str, meta: DebateMeta
    ) -> AsyncIterator[DebateArgument]:
        shared_context = f"""Topic: {article['title']}
Debate question: {meta.question}
Red position: {meta.red.position}
Blue position: {meta.blue.position}

{research_context}"""

        red_messages = [SystemMessage(content=_RED_ROUNDS_PROMPT), HumanMessage(content=shared_context + "\n\nOutput your 7 red rounds as NDJSON now.")]
        blue_messages = [SystemMessage(content=_BLUE_ROUNDS_PROMPT), HumanMessage(content=shared_context + "\n\nOutput your 7 blue rounds as NDJSON now.")]

        red_q: asyncio.Queue = asyncio.Queue()
        blue_q: asyncio.Queue = asyncio.Queue()

        async def fill_queue(stream, q, label: str):
            try:
                async for item in stream:
                    await q.put(item)
            except Exception as e:
                log.warning("debate.fill_queue[%s] failed: %s", label, e)
            finally:
                await q.put(None)

        red_task = asyncio.create_task(fill_queue(_parse_ndjson_stream(self._red_llm, red_messages, "red"), red_q, "red"))
        blue_task = asyncio.create_task(fill_queue(_parse_ndjson_stream(self._blue_llm, blue_messages, "blue"), blue_q, "blue"))

        red_done = False
        blue_done = False
        while not (red_done and blue_done):
            if not red_done:
                item = await red_q.get()
                if item is None:
                    red_done = True
                else:
                    yield item
            if not blue_done:
                item = await blue_q.get()
                if item is None:
                    blue_done = True
                else:
                    yield item

        await asyncio.gather(red_task, blue_task)

    async def build_challenge_reply(
        self, topic: str, question: str, red_position: str, blue_position: str, challenge: str
    ) -> "_ChallengeResponse":
        context = f"""Debate topic: {topic}
Question: {question}
Red position: {red_position}
Blue position: {blue_position}

User challenge: {challenge}"""

        red_messages = [SystemMessage(content=_RED_CHALLENGE_PROMPT), HumanMessage(content=context)]
        blue_messages = [SystemMessage(content=_BLUE_CHALLENGE_PROMPT), HumanMessage(content=context)]

        for attempt in range(3):
            try:
                red_reply, blue_reply = await asyncio.gather(
                    self._red_challenge_llm.ainvoke(red_messages),
                    self._blue_challenge_llm.ainvoke(blue_messages),
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise
                log.warning("Challenge LLM call failed (attempt %d/3): %s", attempt + 1, e)
                await asyncio.sleep(1)
        red_reply.side_id = "red"
        blue_reply.side_id = "blue"
        return _ChallengeResponse(red_reply=red_reply, blue_reply=blue_reply)


class _ChallengeResponse(BaseModel):
    red_reply: DebateArgument
    blue_reply: DebateArgument
