import pytest
from unittest.mock import AsyncMock, MagicMock
from app.path_analyzer import PathAnalyzer, PathData, PathNode, PathEdge, CuriosityInsight

@pytest.mark.asyncio
async def test_path_analyzer_analyze():
    analyzer = PathAnalyzer()
    
    # Mock structured output
    mock_insight = CuriosityInsight(
        pattern="Test pattern",
        theme="Test theme",
        most_unexpected_jump="Jump X to Y",
        rabbit_hole_depth="wide wanderer",
        next_recommendation="Topic Z"
    )
    mock_nodes = [
        PathNode(id="topic-1", title="Topic 1", order=1, summary="S1", why_interesting="W1"),
        PathNode(id="topic-2", title="Topic 2", order=2, summary="S2", why_interesting="W2"),
        PathNode(id="topic-3", title="Topic 3", order=3, summary="S3", why_interesting="W3")
    ]
    mock_edges = [
        PathEdge(source="topic-1", target="topic-2", transition="T1"),
        PathEdge(source="topic-2", target="topic-3", transition="T2")
    ]
    
    mock_result = PathData(
        session_id="test-session",
        nodes=mock_nodes,
        edges=mock_edges,
        insight=mock_insight,
        total_topics=3,
        session_duration_minutes=10
    )
    
    analyzer._structured_llm = AsyncMock()
    analyzer._structured_llm.ainvoke.return_value = mock_result
    
    history = [["T1", "R1"], ["T2", "R2"], ["T3", "R3"]]
    interests = ["tag1"]
    meta = {"created_at": 1600000000}
    
    result = await analyzer.analyze("session-123", history, interests, meta)
    
    assert result.session_id == "session-123"
    assert len(result.nodes) == 3
    assert len(result.edges) == 2
    assert result.insight.pattern == "Test pattern"
