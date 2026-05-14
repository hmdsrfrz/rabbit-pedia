import json
import logging
import os
import time
from typing import Optional

import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

log = logging.getLogger("rabbitpedia.session")
logging.basicConfig(level=logging.INFO)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SESSION_TTL = 86400       # 24 hours in seconds
EXPIRY_WARN_THRESHOLD = 7200  # 2 hours in seconds
MAX_MESSAGES = 20         # 10 user/assistant pairs

_redis: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


class SessionStore:
    def __init__(self):
        self._r = get_redis()

    async def get_history(self, session_id: str) -> list[dict]:
        try:
            key = f"session:{session_id}:messages"
            raw = await self._r.lrange(key, 0, -1)
            history = [json.loads(m) for m in raw]
            log.info("session.get_history sid=%s items=%d", session_id, len(history))
            return history
        except Exception as e:
            log.warning("session.get_history FAILED sid=%s err=%s", session_id, e)
            return []

    async def add_message_pair(self, session_id: str, user_msg: str, ai_summary: str) -> None:
        try:
            key = f"session:{session_id}:messages"
            pipe = self._r.pipeline()
            pipe.rpush(key, json.dumps({"role": "user", "content": user_msg}))
            pipe.rpush(key, json.dumps({"role": "assistant", "content": ai_summary}))
            pipe.ltrim(key, -MAX_MESSAGES, -1)
            pipe.expire(key, SESSION_TTL)
            await pipe.execute()
            await self._refresh_meta(session_id)
            log.info("session.add_message_pair sid=%s", session_id)
        except Exception as e:
            log.warning("session.add_message_pair FAILED sid=%s err=%s", session_id, e)

    async def _refresh_meta(self, session_id: str) -> None:
        try:
            meta_key = f"session:{session_id}:meta"
            now = str(int(time.time()))
            pipe = self._r.pipeline()
            pipe.hsetnx(meta_key, "created_at", now)
            pipe.hset(meta_key, "last_active", now)
            pipe.expire(meta_key, SESSION_TTL)
            await pipe.execute()
        except Exception:
            pass

    async def add_interest(self, session_id: str, tag: str, delta: int = 1) -> None:
        try:
            key = f"session:{session_id}:interests"
            tag = tag.strip()[:80]
            if not tag:
                return
            await self._r.zincrby(key, delta, tag)
            await self._r.expire(key, SESSION_TTL)
            log.info("session.add_interest sid=%s tag=%s delta=%d", session_id, tag, delta)
        except Exception as e:
            log.warning("session.add_interest FAILED sid=%s tag=%s err=%s", session_id, tag, e)

    async def get_top_interests(self, session_id: str, n: int = 5) -> list[str]:
        try:
            key = f"session:{session_id}:interests"
            raw = await self._r.zrevrange(key, 0, n - 1, withscores=True)
            tags = [tag for tag, score in raw if score > 0]
            log.info("session.get_top_interests sid=%s result=%s", session_id, tags)
            return tags
        except Exception as e:
            log.warning("session.get_top_interests FAILED sid=%s err=%s", session_id, e)
            return []

    async def add_user_facts(self, session_id: str, facts: dict[str, str]) -> None:
        try:
            if not facts:
                return
            key = f"session:{session_id}:user_facts"
            clean = {k: v[:200] for k, v in facts.items() if v}
            if not clean:
                return
            await self._r.hset(key, mapping=clean)
            await self._r.expire(key, SESSION_TTL)
        except Exception:
            pass

    async def get_user_facts(self, session_id: str) -> dict[str, str]:
        try:
            key = f"session:{session_id}:user_facts"
            return await self._r.hgetall(key) or {}
        except Exception:
            return {}

    async def get_meta(self, session_id: str) -> dict:
        try:
            meta_key = f"session:{session_id}:meta"
            raw = await self._r.hgetall(meta_key)
            return {k: int(v) for k, v in raw.items() if v.isdigit()}
        except Exception:
            return {}

    async def check_expiry_warning(self, session_id: str) -> bool:
        """Returns True once when TTL < 2h and warning hasn't been shown yet."""
        try:
            meta_key = f"session:{session_id}:meta"
            already_warned = await self._r.hget(meta_key, "expiry_warned")
            if already_warned == "1":
                return False
            ttl = await self._r.ttl(meta_key)
            if ttl < 0:
                return False
            if 0 < ttl < EXPIRY_WARN_THRESHOLD:
                await self._r.hset(meta_key, "expiry_warned", "1")
                return True
            return False
        except Exception:
            return False
