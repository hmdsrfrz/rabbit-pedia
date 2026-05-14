import time
from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from app.history_parser import HistoryParser
from app.llm_client import get_llm


class PathNode(BaseModel):
    id: str
    title: str
    order: int
    summary: str
    why_interesting: str


class PathEdge(BaseModel):
    source: str
    target: str
    transition: str


class CuriosityInsight(BaseModel):
    pattern: str
    theme: str
    most_unexpected_jump: str
    rabbit_hole_depth: str
    next_recommendation: str


class PathData(BaseModel):
    session_id: str
    nodes: List[PathNode]
    edges: List[PathEdge]
    insight: CuriosityInsight
    total_topics: int
    session_duration_minutes: int


_SYSTEM_PROMPT = """
You are a curiosity cartographer for RabbitPedia.

You receive a user's session history — the sequence of topics they
explored and the conversations they had. Your job is to build a
beautiful map of their intellectual journey and reveal what their
curiosity pattern says about them.

Return ONLY valid JSON matching the schema. No markdown, no explanation.

Node construction rules:
- Each distinct topic the user queried becomes a node
- order reflects the sequence they explored (1 = first)
- summary: one line explaining what this topic is, written for someone
  who has never heard of it
- why_interesting: infer from context what specifically pulled this
  user to this topic — not generic, specific to their conversation

Edge construction rules:
- Create an edge between consecutive topics
- Also create edges between non-consecutive topics if the conversation
  reveals a thematic connection the user was chasing
- transition: be specific and human — "they asked about the aftermath
  and ended up here" not "related topic"
- Edges should feel like they tell a story of the user's thinking

Insight rules:
- pattern: one punchy line about HOW they explore
  e.g. "You follow the losers, not the winners"
  "You always ask what happened next"
  "You're drawn to the moment things broke"
- theme: the single hidden thread connecting all their topics
- most_unexpected_jump: the transition that reveals something
  surprising about their curiosity
- rabbit_hole_depth classification:
  "surface skimmer" | "focused diver" | "wide wanderer" | "deep obsessive"
- next_recommendation: a topic they would love but haven't found yet

Tone: warm, insightful, slightly poetic. Never clinical.
"""


class PathAnalyzer:
    def __init__(self):
        llm = get_llm(model="llama-3.3-70b-versatile", temperature=0.7, max_tokens=4000)
        self._structured_llm = llm.with_structured_output(PathData)
        self._parser = HistoryParser()

    async def analyze(self, session_id: str, history: List[List[str]], interests: List[str], meta: dict) -> PathData:
        formatted_history = self._parser.format_for_prompt(history)
        topic_count = len(self._parser.parse(history))

        duration = 0
        if "created_at" in meta:
            duration = int((time.time() - meta["created_at"]) / 60)

        user_msg = f"""
Session history:
{formatted_history}

User interest tags: {interests}
Session duration: {duration} minutes
Number of topics explored: {topic_count}

Build the curiosity path.
"""
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_msg)
        ]

        result = await self._structured_llm.ainvoke(messages)
        result.session_id = session_id
        result.total_topics = topic_count
        result.session_duration_minutes = duration
        return result
