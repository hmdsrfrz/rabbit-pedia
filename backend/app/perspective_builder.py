from typing import List
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from app.wikipedia_fetcher import Article
from app.llm_client import get_llm


class Narrator(BaseModel):
    id: str     # slug e.g. "ottoman-scholar"
    name: str   # e.g. "An Ottoman Scholar, 1453"
    stance: str # one line: their relationship to the topic
    color: str  # hex color for their card accent


class PerspectiveSection(BaseModel):
    narrator: Narrator
    title: str               # their version of the headline
    body: str                # 3-4 paragraphs, written AS this narrator
    what_they_emphasize: str # one line: what they focus on
    what_they_omit: str      # one line: what they conveniently ignore
    most_revealing_line: str # the single most striking sentence from body


class PerspectiveData(BaseModel):
    topic: str
    origin_summary: str          # neutral one-liner, shown at top
    perspectives: List[PerspectiveSection]  # always 4 perspectives


_SYSTEM_PROMPT = """
You are a perspective architect for RabbitPedia.

Given a Wikipedia article, generate exactly 4 perspectives on the topic.
Each perspective is written AS a specific narrator — a real type of person
with a name, era, cultural context, and emotional relationship to the topic.

Return ONLY valid JSON matching the schema. No markdown, no explanation.

Narrator selection rules:
- Pick narrators who would genuinely disagree with each other
- Include at least one narrator from a non-Western cultural context
- Include at least one narrator from a different historical era than the topic
- Include one narrator who "lost" or was on the opposing side of the topic
- Include one narrator who is a modern expert or descendant affected by it
- Make narrators specific: not "a Roman soldier" but "A Carthaginian
  merchant whose city was destroyed by Rome, 146 BC"

Body writing rules:
- Write each body IN FIRST PERSON as that narrator
- Use vocabulary, concerns, and values authentic to that narrator
- Do not be neutral — each narrator has opinions, grief, pride, or anger
- 3-4 paragraphs, each paragraph a distinct aspect of the topic
- Make it feel like reading a primary source, not a Wikipedia summary

what_they_omit: be honest about what this narrator would conveniently
ignore, downplay, or never mention — their blind spot

most_revealing_line: the single sentence from body that best captures
their unique perspective — pull it exactly from the body text

Color assignment (use these, pick the most fitting per narrator):
- Opposing/defeated side: #c0392b (red)
- Non-Western perspective: #2980b9 (blue)
- Historical era narrator: #8e44ad (purple)
- Modern expert/descendant: #27ae60 (green)
- Default: #e67e22 (orange)
"""


class PerspectiveBuilder:
    def __init__(self):
        llm = get_llm(model="llama-3.3-70b-versatile", temperature=0.7, max_tokens=5000)
        self._structured_llm = llm.with_structured_output(PerspectiveData)

    async def build(self, article: Article) -> PerspectiveData:
        user_msg = f"""
Topic: {article['title']}
Wikipedia summary: {article['summary'][:800]}

Generate 4 perspectives.
"""
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_msg)
        ]
        return await self._structured_llm.ainvoke(messages)
