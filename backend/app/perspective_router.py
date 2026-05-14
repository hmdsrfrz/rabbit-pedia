from fastapi import APIRouter, HTTPException, Query
from app.wikipedia_fetcher import WikipediaFetcher
from app.perspective_builder import PerspectiveBuilder, PerspectiveData
import asyncio
from functools import partial

router = APIRouter()
_fetcher = WikipediaFetcher()
_perspective_builder = PerspectiveBuilder()

@router.get("/perspective", response_model=PerspectiveData)
async def get_perspective(query: str = Query(..., description="The topic to generate multiple perspectives for")):
    loop = asyncio.get_event_loop()
    
    # 1. WikipediaFetcher.search(query) -> article
    article = await loop.run_in_executor(None, partial(_fetcher.search, query))
    if not article.get("title"):
        raise HTTPException(status_code=404, detail="Topic not found on Wikipedia")
    
    # 2. PerspectiveBuilder.build(article) -> PerspectiveData
    perspective_data = await _perspective_builder.build(article)
    
    return perspective_data
