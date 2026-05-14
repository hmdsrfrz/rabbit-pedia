import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, AsyncMock, MagicMock
from app.perspective_builder import PerspectiveData, PerspectiveSection, Narrator

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_perspective_success():
    mock_article = {"title": "Test Topic", "summary": "Summary", "url": "url"}
    mock_perspective_data = PerspectiveData(
        topic="Test Topic",
        origin_summary="Summary",
        perspectives=[
             PerspectiveSection(
                narrator=Narrator(id=f"n{i}", name=f"Narrator {i}", icon="👤", stance=f"Stance {i}", color="#000000"),
                title=f"Title {i}",
                body=f"Body {i}",
                what_they_emphasize=f"E {i}",
                what_they_omit=f"O {i}",
                most_revealing_line=f"R {i}"
            )
            for i in range(4)
        ]
    )

    with patch("app.perspective_router._fetcher.search", return_value=mock_article), \
         patch("app.perspective_router._perspective_builder.build", new_callable=AsyncMock, return_value=mock_perspective_data):
        
        response = client.get("/perspective?query=Test")
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "Test Topic"
        assert len(data["perspectives"]) == 4

def test_get_perspective_missing_query():
    response = client.get("/perspective")
    assert response.status_code == 422
