import json
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


async def _collect_events(response) -> list[dict]:
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
            if events[-1]["type"] == "done":
                break
    return events


@pytest.mark.asyncio
async def test_chat_emits_thinking_then_section_then_done():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/chat",
            json={"session_id": "test-session", "message": "black holes", "deep": False},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            events = await _collect_events(response)

    types = [e["type"] for e in events]
    assert types[0] == "thinking"
    assert "section" in types
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_chat_section_has_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/chat",
            json={"session_id": "test-session-2", "message": "the moon", "deep": False},
        ) as response:
            events = await _collect_events(response)

    section_event = next(e for e in events if e["type"] == "section")
    s = section_event["content"]
    assert s["heading"]
    assert s["body"]
    assert isinstance(s["did_you_know"], list)
    assert len(s["did_you_know"]) >= 2
    assert s["two_cents"]
    assert isinstance(s["sources"], list)
    assert isinstance(s["explore_further"]["from_article"], list)
    assert isinstance(s["explore_further"]["you_might_like"], list)


@pytest.mark.asyncio
async def test_chat_done_event_has_timing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/chat",
            json={"session_id": "test-session-3", "message": "gravity", "deep": False},
        ) as response:
            events = await _collect_events(response)

    done_event = next(e for e in events if e["type"] == "done")
    assert "total_ms" in done_event["content"]
