import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, AsyncMock
from app.path_analyzer import PathData, CuriosityInsight

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_path_success():
    mock_history = [["T1", "R1"], ["T2", "R2"], ["T3", "R3"]]
    mock_interests = ["tag"]
    mock_meta = {"created_at": 100}
    
    mock_path_data = PathData(
        session_id="test",
        nodes=[],
        edges=[],
        insight=CuriosityInsight(pattern="P", theme="T", most_unexpected_jump="J", rabbit_hole_depth="skimmer", next_recommendation="R"),
        total_topics=3,
        session_duration_minutes=5
    )

    with patch("app.path_router._session_store.get_history", new_callable=AsyncMock, return_value=mock_history), \
         patch("app.path_router._session_store.get_interests", new_callable=AsyncMock, return_value=mock_interests), \
         patch("app.path_router._session_store.get_meta", new_callable=AsyncMock, return_value=mock_meta), \
         patch("app.path_router._path_analyzer.analyze", new_callable=AsyncMock, return_value=mock_path_data):
        
        response = client.get("/path?session_id=test")
        assert response.status_code == 200
        assert response.json()["total_topics"] == 3

@pytest.mark.asyncio
async def test_get_path_empty():
    with patch("app.path_router._session_store.get_history", new_callable=AsyncMock, return_value=[]):
        response = client.get("/path?session_id=empty")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_path_too_short():
    mock_history = [["T1", "R1"], ["T2", "R2"]]
    with patch("app.path_router._session_store.get_history", new_callable=AsyncMock, return_value=mock_history):
        response = client.get("/path?session_id=short")
        assert response.status_code == 400
