import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, AsyncMock, MagicMock
from app.debate_builder import DebateData, DebateSide

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_debate_success():
    mock_article = {"title": "Test Topic", "summary": "Summary", "url": "url"}
    mock_debate_data = DebateData(
        topic="Test Topic",
        question="Is this a test?",
        context="Context",
        red=DebateSide(id="red", label="Against", position="Stance A", icon="🔴", color="#c0392b"),
        blue=DebateSide(id="blue", label="For", position="Stance B", icon="🔵", color="#2980b9"),
        rounds=[],
        verdict="Verdict"
    )

    with patch("app.debate_router._fetcher.search", return_value=mock_article), \
         patch("app.debate_router._debate_builder.build", new_callable=AsyncMock, return_value=mock_debate_data):
        
        response = client.get("/debate?query=Test")
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "Test Topic"
        assert data["question"] == "Is this a test?"

def test_get_debate_missing_query():
    response = client.get("/debate")
    assert response.status_code == 422
