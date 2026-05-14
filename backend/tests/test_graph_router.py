import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, AsyncMock, MagicMock
from app.graph_builder import GraphData, GraphNode, GraphEdge

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_graph_success():
    mock_article = {"title": "Rabbit", "summary": "Summary", "url": "url"}
    mock_links = [f"Link {i}" for i in range(200)]
    mock_graph_data = GraphData(
        origin="Rabbit",
        nodes=[GraphNode(id="Rabbit", summary="A fluffy mammal")] + 
              [GraphNode(id=f"Node {i}", summary=f"Summary {i}") for i in range(80)],
        edges=[GraphEdge(source="Rabbit", target=f"Node {i}", label="is related to", explanation="exp") for i in range(80)]
    )

    with patch("app.graph_router._fetcher.search", return_value=mock_article), \
         patch("app.graph_router._fetcher.get_links", new_callable=AsyncMock, return_value=mock_links), \
         patch("app.graph_router._graph_builder.build", new_callable=AsyncMock, return_value=mock_graph_data):
        
        response = client.get("/graph?query=Rabbit")
        assert response.status_code == 200
        data = response.json()
        assert data["origin"] == "Rabbit"
        assert len(data["nodes"]) >= 81
        assert len(data["edges"]) >= 80

def test_get_graph_missing_query():
    response = client.get("/graph")
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_get_graph_not_found():
    mock_article = {"title": "", "summary": ""}
    with patch("app.graph_router._fetcher.search", return_value=mock_article):
        response = client.get("/graph?query=NonExistentTopic")
        assert response.status_code == 404
