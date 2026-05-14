import pytest
from app.response_formatter import ResponseFormatter
from app.wikipedia_fetcher import Article


PRIMARY: Article = {
    "title": "The Strokes",
    "summary": (
        "The Strokes are an American rock band formed in New York City in 1998. "
        "They were a leading group of the early-2000s garage rock revival and post-punk revival movements. "
        "Their debut album Is This It (2001) is widely considered one of the most influential albums of the 21st century."
    ),
    "url": "https://en.wikipedia.org/wiki/The_Strokes",
    "see_also": ["Garage rock revival", "Post-punk revival", "Indie rock"],
    "image_url": "",
}

SECONDARY: Article = {
    "title": "Garage rock revival",
    "summary": (
        "Garage rock revival was a musical movement of the late 1990s and early 2000s that drew from "
        "1960s garage rock and post-punk. It produced bands like The Strokes, The White Stripes, and The Hives."
    ),
    "url": "https://en.wikipedia.org/wiki/Garage_rock_revival",
    "see_also": [],
    "image_url": "",
}

TERTIARY: Article = {
    "title": "Post-punk revival",
    "summary": (
        "Post-punk revival is a genre of indie rock that emerged in the early 2000s, drawing from "
        "post-punk and new wave. It included bands like Interpol, Franz Ferdinand, and Bloc Party."
    ),
    "url": "https://en.wikipedia.org/wiki/Post-punk_revival",
    "see_also": [],
    "image_url": "",
}


@pytest.mark.asyncio
async def test_you_might_like_includes_at_least_one_sentence_question():
    formatter = ResponseFormatter()
    result = await formatter.format("The Strokes", PRIMARY)
    items = result.explore_further.you_might_like
    assert any("?" in item for item in items), (
        f"No sentence-style question in you_might_like: {items}"
    )


@pytest.mark.asyncio
async def test_deep_mode_populates_key_concepts():
    formatter = ResponseFormatter()
    result = await formatter.format("The Strokes", [PRIMARY, SECONDARY, TERTIARY])
    assert result.key_concepts is not None
    assert len(result.key_concepts) >= 3


@pytest.mark.asyncio
async def test_deep_mode_body_is_richer():
    formatter = ResponseFormatter()
    result = await formatter.format("The Strokes", [PRIMARY, SECONDARY, TERTIARY])
    paragraphs = [p for p in result.body.split("\n\n") if p.strip()]
    assert len(paragraphs) >= 3, f"Deep body too thin: {len(paragraphs)} paragraphs"


@pytest.mark.asyncio
async def test_sources_always_included_when_url_provided():
    formatter = ResponseFormatter()
    result = await formatter.format("The Strokes", PRIMARY)
    assert len(result.sources) >= 1
    assert any(s.url == PRIMARY["url"] for s in result.sources)
