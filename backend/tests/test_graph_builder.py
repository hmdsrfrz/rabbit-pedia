import pytest
from unittest.mock import AsyncMock, MagicMock
from app.graph_builder import GraphBuilder, GraphData, GraphNode, GraphEdge
from app.wikipedia_fetcher import Article

@pytest.mark.asyncio
async def test_graph_builder_build():
    builder = GraphBuilder()
    
    # Mock the structured LLM
    mock_result = GraphData(
        origin="Rabbit",
        nodes=[GraphNode(id="Rabbit", summary="A fluffy mammal")] + 
              [GraphNode(id=f"Node {i}", summary=f"Summary {i}") for i in range(80)],
        edges=[GraphEdge(source="Rabbit", target=f"Node {i}", label="is related to", explanation="Connection explanation") for i in range(80)]
    )
    
    builder._structured_llm = AsyncMock()
    builder._structured_llm.ainvoke.return_value = mock_result
    
    article = Article(title="Rabbit", summary="Summary", url="url", see_also=[], image_url="")
    links = ["Link 1", "Link 2"]
    
    result = await builder.build(article, links)
    
    assert isinstance(result, GraphData)
    assert result.origin == "Rabbit"
    assert 80 <= len(result.nodes) <= 101
    assert 80 <= len(result.edges) <= 101
    assert any(node.id == "Rabbit" for node in result.nodes)
