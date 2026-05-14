from fastapi import APIRouter, HTTPException, Query
from app.session_store import SessionStore
from app.path_analyzer import PathAnalyzer, PathData
from app.history_parser import HistoryParser
import asyncio

router = APIRouter()
_session_store = SessionStore()
_path_analyzer = PathAnalyzer()
_parser = HistoryParser()

@router.get("/path", response_model=PathData)
async def get_curiosity_path(session_id: str = Query(..., description="The user's session ID")):
    # 1. SessionStore.get_history(session_id) -> history
    history = await _session_store.get_history(session_id)
    
    # 4. If history is empty: return 404
    if not history:
        raise HTTPException(status_code=404, detail="No curiosity trail found. Start exploring on RabbitPedia first.")
    
    # 5. If fewer than 3 topics: return 400
    topics = _parser.parse(history)
    if len(topics) < 3:
        raise HTTPException(status_code=400, detail="Explore at least 3 topics to generate your curiosity path.")
    
    # 2. SessionStore.get_interests(session_id) -> interests
    interests = await _session_store.get_top_interests(session_id)
    meta = await _session_store.get_meta(session_id)
    
    # 8. PathAnalyzer.analyze(...) -> PathData
    path_data = await _path_analyzer.analyze(session_id, history, interests, meta)
    
    return path_data
