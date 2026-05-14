import asyncio
import json
from functools import partial
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.wikipedia_fetcher import WikipediaFetcher
from app.debate_builder import DebateBuilder, build_research_context

router = APIRouter()
_fetcher = WikipediaFetcher()
_debate_builder = DebateBuilder()


async def _stream_debate(query: str):
    loop = asyncio.get_event_loop()
    article = await loop.run_in_executor(None, partial(_fetcher.search, query))
    if not article.get("title"):
        yield f"data: {json.dumps({'type': 'error', 'content': 'Topic not found on Wikipedia'})}\n\n"
        return

    research_context = await build_research_context(article)

    try:
        meta = await _debate_builder.build_meta(article, research_context)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'meta', 'content': meta.model_dump()})}\n\n"

    async for round_arg in _debate_builder.stream_rounds(article, research_context, meta):
        yield f"data: {json.dumps({'type': 'round', 'content': round_arg.model_dump()})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.get("/debate")
async def get_debate(query: str = Query(...)):
    return StreamingResponse(
        _stream_debate(query),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ChallengeRequest(BaseModel):
    topic: str
    question: str
    red_position: str
    blue_position: str
    challenge: str


@router.post("/debate/challenge")
async def post_challenge(req: ChallengeRequest):
    try:
        result = await _debate_builder.build_challenge_reply(
            req.topic, req.question, req.red_position, req.blue_position, req.challenge
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "red_reply": result.red_reply.model_dump(),
        "blue_reply": result.blue_reply.model_dump(),
    }
