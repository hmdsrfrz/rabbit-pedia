import pytest
from app.response_formatter import ResponseFormatter, ResponseSection
from app.wikipedia_fetcher import Article


SAMPLE_ARTICLE: Article = {
    "title": "Black hole",
    "summary": "A black hole is a region of spacetime where gravity is so strong that nothing can escape.",
    "url": "https://en.wikipedia.org/wiki/Black_hole",
    "see_also": ["Neutron star", "Quasar", "Hawking radiation", "Event horizon"],
}

EMPTY_ARTICLE: Article = {
    "title": "",
    "summary": "",
    "url": "",
    "see_also": [],
}


@pytest.mark.asyncio
async def test_format_returns_response_section():
    formatter = ResponseFormatter()
    result = await formatter.format("black holes", SAMPLE_ARTICLE)
    assert isinstance(result, ResponseSection)


@pytest.mark.asyncio
async def test_format_heading_and_body_are_populated():
    formatter = ResponseFormatter()
    result = await formatter.format("black holes", SAMPLE_ARTICLE)
    assert result.heading
    assert len(result.body) > 100


@pytest.mark.asyncio
async def test_format_sources_only_use_provided_url():
    formatter = ResponseFormatter()
    result = await formatter.format("black holes", SAMPLE_ARTICLE)
    for source in result.sources:
        assert source.url == SAMPLE_ARTICLE["url"], (
            f"Fabricated URL detected: {source.url}"
        )


@pytest.mark.asyncio
async def test_format_explore_further_from_article_uses_see_also():
    formatter = ResponseFormatter()
    result = await formatter.format("black holes", SAMPLE_ARTICLE)
    from_article = [t.lower() for t in result.explore_further.from_article]
    see_also_lower = [s.lower() for s in SAMPLE_ARTICLE["see_also"]]
    # At least one see_also item should appear in from_article
    assert any(item in see_also_lower for item in from_article)


@pytest.mark.asyncio
async def test_format_did_you_know_has_facts():
    formatter = ResponseFormatter()
    result = await formatter.format("black holes", SAMPLE_ARTICLE)
    assert len(result.did_you_know) >= 2


@pytest.mark.asyncio
async def test_format_key_concepts_none_or_list():
    formatter = ResponseFormatter()
    result = await formatter.format("black holes", SAMPLE_ARTICLE)
    assert result.key_concepts is None or isinstance(result.key_concepts, list)


@pytest.mark.asyncio
async def test_format_empty_article_still_returns_section():
    formatter = ResponseFormatter()
    result = await formatter.format("nonexistent topic xyz", EMPTY_ARTICLE)
    assert isinstance(result, ResponseSection)
    assert result.heading
