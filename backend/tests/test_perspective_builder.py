import pytest
from unittest.mock import AsyncMock, MagicMock
from app.perspective_builder import PerspectiveBuilder, PerspectiveData, PerspectiveSection, Narrator
from app.wikipedia_fetcher import Article

@pytest.mark.asyncio
async def test_perspective_builder_build():
    builder = PerspectiveBuilder()
    
    # Mock the structured LLM
    mock_perspectives = [
        PerspectiveSection(
            narrator=Narrator(id=f"n{i}", name=f"Narrator {i}", icon="👤", stance=f"Stance {i}", color="#000000"),
            title=f"Title {i}",
            body=f"Body paragraph 1. Body paragraph 2. Body paragraph 3. Body paragraph 4.",
            what_they_emphasize=f"Emphasize {i}",
            what_they_omit=f"Omit {i}",
            most_revealing_line=f"Revealing line {i}"
        )
        for i in range(4)
    ]

    mock_result = PerspectiveData(
        topic="Test Topic",
        origin_summary="A neutral summary.",
        perspectives=mock_perspectives
    )
    
    builder._structured_llm = AsyncMock()
    builder._structured_llm.ainvoke.return_value = mock_result
    
    article = Article(title="Test Topic", summary="Summary", url="url", see_also=[], image_url="")
    
    result = await builder.build(article)
    
    assert isinstance(result, PerspectiveData)
    assert len(result.perspectives) == 4
    for p in result.perspectives:
        assert p.narrator.name is not None
        assert p.most_revealing_line != ""
        assert len(p.body.split('.')) >= 3
