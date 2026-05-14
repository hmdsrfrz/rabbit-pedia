import asyncio
import pytest
from app.research_agent import ResearchAgent


@pytest.mark.asyncio
async def test_run_yields_tokens_for_topic_query():
    agent = ResearchAgent()
    tokens = []
    async for token in agent.run("black holes"):
        tokens.append(token)
        if len(tokens) >= 3:
            break
    assert len(tokens) >= 1
    assert all(isinstance(t, str) for t in tokens)


@pytest.mark.asyncio
async def test_run_with_article_context_yields_tokens():
    from app.wikipedia_fetcher import WikipediaFetcher
    fetcher = WikipediaFetcher()
    article = fetcher.search("black holes")
    agent = ResearchAgent()
    tokens = []
    async for token in agent.run("black holes", article=article):
        tokens.append(token)
        if len(tokens) >= 3:
            break
    assert len(tokens) >= 1
