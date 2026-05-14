import logging
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.observability import log_phase, PHASE_LOGGER_NAME


@pytest.mark.asyncio
async def test_log_phase_emits_structured_record(caplog):
    caplog.set_level(logging.INFO, logger=PHASE_LOGGER_NAME)
    log_phase(
        phase="wikipedia_fetch",
        session_id="sid-abc",
        elapsed_ms=123,
        ok=True,
        extra={"title": "Black hole"},
    )
    records = [r for r in caplog.records if r.name == PHASE_LOGGER_NAME]
    assert any(
        r.phase == "wikipedia_fetch" and r.session_id == "sid-abc"
        and r.elapsed_ms == 123 and r.ok is True
        and getattr(r, "title", None) == "Black hole"
        for r in records
    )


@pytest.mark.asyncio
async def test_log_phase_marks_errors():
    import logging as _l
    logger = _l.getLogger(PHASE_LOGGER_NAME)
    captured: list[_l.LogRecord] = []

    class _H(_l.Handler):
        def emit(self, record): captured.append(record)
    h = _H(); h.setLevel(_l.INFO); logger.addHandler(h); logger.setLevel(_l.INFO)
    try:
        log_phase(phase="format", session_id="x", elapsed_ms=5, ok=False, extra={"err": "boom"})
    finally:
        logger.removeHandler(h)
    assert any(r.ok is False and r.phase == "format" and getattr(r, "err", "") == "boom" for r in captured)


@pytest.mark.asyncio
async def test_chat_emits_phase_logs(caplog):
    caplog.set_level(logging.INFO, logger=PHASE_LOGGER_NAME)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream(
            "POST", "/chat",
            json={"session_id": "obs-sid", "message": "neutron stars", "deep": False},
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and '"done"' in line:
                    break

    phases = {r.phase for r in caplog.records if r.name == PHASE_LOGGER_NAME and hasattr(r, "phase")}
    assert "wikipedia_fetch" in phases
    assert "format" in phases
    assert "stream" in phases


@pytest.mark.asyncio
async def test_feedback_endpoint_accepts_thumbs_up():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/feedback",
            json={"session_id": "fb-sid", "message_id": "msg-1", "rating": "up"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_feedback_endpoint_accepts_thumbs_down():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/feedback",
            json={"session_id": "fb-sid", "message_id": "msg-2", "rating": "down"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_feedback_endpoint_rejects_invalid_rating():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/feedback",
            json={"session_id": "fb-sid", "message_id": "msg-3", "rating": "sideways"},
        )
    assert resp.status_code == 422
