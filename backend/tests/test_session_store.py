import pytest
import logging
from app.session_store import SessionStore


@pytest.mark.asyncio
async def test_interest_round_trip_returns_tagged_term():
    store = SessionStore()
    sid = "test-interest-roundtrip"
    try:
        await store._r.delete(f"session:{sid}:interests")
    except Exception:
        pytest.skip("redis not reachable")
    await store.add_interest(sid, "neutron stars", 1)
    top = await store.get_top_interests(sid, 5)
    assert "neutron stars" in top


@pytest.mark.asyncio
async def test_add_interest_emits_log(caplog):
    store = SessionStore()
    sid = "test-interest-log"
    try:
        await store._r.ping()
    except Exception:
        pytest.skip("redis not reachable")
    with caplog.at_level(logging.INFO, logger="rabbitpedia.session"):
        await store.add_interest(sid, "quantum entanglement", 1)
    assert any(
        "add_interest" in r.getMessage() and "quantum entanglement" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_get_top_interests_emits_log(caplog):
    store = SessionStore()
    sid = "test-interest-get-log"
    try:
        await store._r.ping()
    except Exception:
        pytest.skip("redis not reachable")
    await store.add_interest(sid, "topic-A", 1)
    with caplog.at_level(logging.INFO, logger="rabbitpedia.session"):
        await store.get_top_interests(sid, 5)
    assert any("get_top_interests" in r.getMessage() for r in caplog.records)
