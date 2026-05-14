from fastapi import APIRouter, HTTPException, Query
from app.wikipedia_fetcher import WikipediaFetcher
from app.graph_builder import GraphBuilder, GraphData
import asyncio
from functools import partial

router = APIRouter()
_fetcher = WikipediaFetcher()
_graph_builder = GraphBuilder()

@router.get("/graph", response_model=GraphData)
async def get_graph(query: str = Query(..., description="The topic to build a knowledge graph for")):
    loop = asyncio.get_event_loop()
    
    # 1. WikipediaFetcher.search(query) -> article
    article = await loop.run_in_executor(None, partial(_fetcher.search, query))
    if not article.get("title"):
        raise HTTPException(status_code=404, detail="Topic not found on Wikipedia")
    
    # 2. WikipediaFetcher.get_links(article.title, limit=500) -> links
    links = await loop.run_in_executor(None, partial(_fetcher.get_links, article["title"], 40))
    
    # 3. GraphBuilder.build(article, links) -> GraphData
    graph_data = await _graph_builder.build(article, links)
    
    return graph_data
