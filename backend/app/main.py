import asyncio
import json
import os
import time
from functools import partial
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from app.wikipedia_fetcher import WikipediaFetcher
from app.response_formatter import ResponseFormatter
from app.session_store import SessionStore
from app.fact_extractor import FactExtractor
from app.router import IntentRouter, ConversationalReplier
from app.query_normaliser import QueryNormaliser
from app.observability import phase_timer, log_phase
from app.graph_router import router as graph_router
from app.debate_router import router as debate_router
from app.perspective_router import router as perspective_router
from app.path_router import router as path_router
from app.connection_router import router as connection_router
from typing import Literal

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_CORS_HEADERS = {"Access-Control-Allow-Origin": "http://localhost:3000"}

@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    import logging, traceback
    logging.getLogger("rabbitpedia").error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
        headers=_CORS_HEADERS,
    )

app.include_router(graph_router)
app.include_router(debate_router)
app.include_router(perspective_router)
app.include_router(path_router)
app.include_router(connection_router)

_fetcher = WikipediaFetcher()
_formatter = ResponseFormatter()
_session_store = SessionStore()
_fact_extractor = FactExtractor()
_router = IntentRouter()
_replier = ConversationalReplier()
_normaliser = QueryNormaliser()


@app.on_event("startup")
async def _startup_check():
    import logging
    log = logging.getLogger("rabbitpedia")
    try:
        pong = await _session_store._r.ping()
        log.info("redis ping: %s (url=%s)", pong, os.getenv("REDIS_URL", "redis://localhost:6379"))
    except Exception as e:
        log.error("REDIS UNREACHABLE — sessions will not persist. err=%s", e)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    deep: bool = False


class InterestRequest(BaseModel):
    session_id: str
    fact: str
    interested: bool


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: Literal["up", "down"]


async def _extract_facts_bg(session_id: str, message: str):
    facts = await _fact_extractor.extract(message)
    if facts:
        await _session_store.add_user_facts(session_id, facts)


async def _stream_chat(request: ChatRequest):
    start = time.time()
    yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

    history = await _session_store.get_history(request.session_id)
    interests = await _session_store.get_top_interests(request.session_id, 5)
    user_facts = await _session_store.get_user_facts(request.session_id)

    asyncio.create_task(_extract_facts_bg(request.session_id, request.message))

    intent = "research"
    if not request.deep:
        intent = await _router.classify(request.message, has_history=bool(history))

    if intent == "conversational":
        with phase_timer("agent_invoke", request.session_id, {"intent": "conversational"}):
            reply_text = await _replier.reply(request.message, history, user_facts)
        section_payload = {
            "heading": "RabbitPedia",
            "body": reply_text,
            "key_concepts": None,
            "did_you_know": [],
            "two_cents": "",
            "sources": [],
            "explore_further": {"from_article": [], "you_might_like": []},
            "image_url": "",
            "conversational": True,
        }
        yield f"data: {json.dumps({'type': 'section', 'content': section_payload})}\n\n"
        await _session_store.add_message_pair(request.session_id, request.message, reply_text[:350])
    else:
        loop = asyncio.get_event_loop()
        with phase_timer("normalise_query", request.session_id, {"original": request.message[:80]}) as ns:
            wiki_query = await _normaliser.normalize(request.message)
            ns["extra"]["normalised"] = wiki_query[:80]
        with phase_timer("wikipedia_fetch", request.session_id, {"deep": request.deep, "query": wiki_query[:80]}) as st:
            if request.deep:
                articles = await loop.run_in_executor(None, partial(_fetcher.deep_search, wiki_query))
                primary = articles[0]
            else:
                primary = await loop.run_in_executor(None, partial(_fetcher.search, wiki_query))
                articles = [primary]
            st["extra"]["articles"] = len(articles)
            st["extra"]["found"] = bool(primary.get("title"))

        if not primary.get("title") or not primary.get("summary"):
            section_payload = {
                "heading": request.message,
                "body": (
                    f"I couldn't find a Wikipedia article for \"{request.message}\". "
                    "Wikipedia returned no matching page, so I won't make anything up. "
                    "Try rephrasing the topic, using a more specific name, or checking the spelling."
                ),
                "key_concepts": None,
                "did_you_know": [],
                "two_cents": "",
                "sources": [],
                "explore_further": {"from_article": [], "you_might_like": []},
                "image_url": "",
                "conversational": False,
                "no_article": True,
            }
            yield f"data: {json.dumps({'type': 'section', 'content': section_payload})}\n\n"
            await _session_store.add_message_pair(
                request.session_id, request.message, f"(no Wikipedia article found for {request.message})"
            )
        else:
            with phase_timer("format", request.session_id, {"articles": len(articles)}):
                section = await _formatter.format(
                    request.message, articles, history, interests, user_facts
                )

            section_payload = section.model_dump()
            section_payload["image_url"] = primary.get("image_url", "")
            section_payload["conversational"] = False
            yield f"data: {json.dumps({'type': 'section', 'content': section_payload})}\n\n"

            ai_summary = f"{section.heading}: {section.body[:350]}"
            await _session_store.add_message_pair(request.session_id, request.message, ai_summary)

    expiry_warning = await _session_store.check_expiry_warning(request.session_id)
    total_ms = int((time.time() - start) * 1000)
    log_phase("stream", request.session_id, total_ms, True, {"intent": intent, "deep": request.deep})
    yield f"data: {json.dumps({'type': 'done', 'content': {'total_ms': total_ms, 'session_expiry_warning': expiry_warning}})}\n\n"


@app.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        _stream_chat(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/interest")
async def interest(req: InterestRequest):
    delta = 1 if req.interested else -1
    await _session_store.add_interest(req.session_id, req.fact, delta)
    return {"ok": True}


@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    try:
        key = f"session:{req.session_id}:feedback"
        await _session_store._r.hset(key, req.message_id, req.rating)
        await _session_store._r.expire(key, 86400)
    except Exception as e:
        log_phase("feedback", req.session_id, 0, False, {"err": str(e)})
    log_phase("feedback", req.session_id, 0, True, {"message_id": req.message_id, "rating": req.rating})
    return {"ok": True}
