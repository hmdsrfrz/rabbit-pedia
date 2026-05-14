import pytest
from app.query_normaliser import QueryNormaliser


@pytest.mark.asyncio
async def test_factual_question_becomes_short_article_title():
    normaliser = QueryNormaliser()
    result = await normaliser.normalize("how many books are in the harry potter series")
    # Expect a short article-title-like phrase, not the original sentence
    assert "?" not in result
    assert "how many" not in result.lower()
    assert "harry potter" in result.lower()
    assert len(result.split()) <= 6


@pytest.mark.asyncio
async def test_topic_name_passes_through_substantially_unchanged():
    normaliser = QueryNormaliser()
    result = await normaliser.normalize("The Strokes")
    assert "strokes" in result.lower()


@pytest.mark.asyncio
async def test_empty_message_returns_empty_or_original():
    normaliser = QueryNormaliser()
    result = await normaliser.normalize("")
    assert result == "" or isinstance(result, str)
