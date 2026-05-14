import pytest
from unittest.mock import AsyncMock, MagicMock
from app.debate_builder import DebateBuilder, DebateData, DebateSide, DebateArgument
from app.wikipedia_fetcher import Article

@pytest.mark.asyncio
async def test_debate_builder_build():
    builder = DebateBuilder()
    
    # Mock the structured LLM
    mock_rounds = []
    for i in range(10):
        side = "red" if i % 2 == 0 else "blue"
        # Adjust for the specific sequence in prompt if needed, 
        # but prompt says 1.red, 2.blue, 3.red, 4.blue, 5.blue, 6.red...
        # Let's just mock what the prompt expects:
        # 1. red: opening
        # 2. blue: opening
        # 3. red: argument
        # 4. blue: argument
        # 5. blue: rebuttal
        # 6. red: rebuttal
        # 7. red: argument
        # 8. blue: argument
        # 9. red: closing
        # 10. blue: closing
    
    sequence = [
        ("red", "opening"), ("blue", "opening"),
        ("red", "argument"), ("blue", "argument"),
        ("blue", "rebuttal"), ("red", "rebuttal"),
        ("red", "argument"), ("blue", "argument"),
        ("red", "closing"), ("blue", "closing")
    ]
    
    mock_rounds = [
        DebateArgument(
            side_id=side, 
            type=arg_type, 
            heading=f"Heading {i}", 
            content=f"Content {i}",
            targets="Claim X" if arg_type == "rebuttal" else None
        )
        for i, (side, arg_type) in enumerate(sequence)
    ]

    mock_result = DebateData(
        topic="Test Topic",
        question="Is this a test?",
        context="A test context.",
        red=DebateSide(id="red", label="Against", position="Stance A", icon="🔴", color="#c0392b"),
        blue=DebateSide(id="blue", label="For", position="Stance B", icon="🔵", color="#2980b9"),
        rounds=mock_rounds,
        verdict="Neutral verdict."
    )
    
    builder._structured_llm = AsyncMock()
    builder._structured_llm.ainvoke.return_value = mock_result
    
    article = Article(title="Test Topic", summary="Summary", url="url", see_also=[], image_url="")
    
    result = await builder.build(article)
    
    assert isinstance(result, DebateData)
    assert len(result.rounds) == 10
    assert result.rounds[4].side_id == "blue"
    assert result.rounds[4].type == "rebuttal"
    assert result.rounds[4].targets is not None
    assert result.rounds[5].side_id == "red"
    assert result.rounds[5].type == "rebuttal"
    assert result.rounds[5].targets is not None
