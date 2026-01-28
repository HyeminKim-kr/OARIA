"""Search Cache Manager

검색 결과 캐싱.
- 티어별 TTL
- Redis 기반 캐싱
"""

import hashlib
import json
import logging
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# 캐시 TTL (초)
CACHE_TTL = {
    "rag": 7 * 24 * 3600,    # 7일
    "epmc": 30 * 24 * 3600,  # 30일
    "web": 7 * 24 * 3600,    # 7일
}


class SearchCacheManager:
    """
    검색 결과 캐시 관리자
    
    Redis를 사용하여 검색 결과 캐싱.
    Redis 없이도 동작 (캐시 미사용)
    """
    
    def __init__(self):
        self._redis_client = None
        self._redis_available = False
        self._memory_cache: dict[str, Any] = {}  # fallback
        
    async def _get_redis(self):
        """Redis 클라이언트 lazy 초기화"""
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis_client.ping()
                self._redis_available = True
                logger.info("Redis connected for cache management")
            except Exception as e:
                logger.warning(f"Redis not available, cache disabled: {e}")
                self._redis_available = False
        return self._redis_client if self._redis_available else None
    
    def _make_cache_key(self, tier: str, query_plan: dict, hypothesis_hash: str) -> str:
        """캐시 키 생성"""
        query_str = json.dumps(query_plan, sort_keys=True)
        content = f"{tier}:{hypothesis_hash}:{query_str}"
        return f"study_plan:cache:{hashlib.md5(content.encode()).hexdigest()}"
    
    async def get(
        self,
        tier: str,
        query_plan: dict,
        hypothesis_hash: str,
    ) -> Optional[dict]:
        """캐시 조회"""
        cache_key = self._make_cache_key(tier, query_plan, hypothesis_hash)
        
        redis = await self._get_redis()
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.info(f"[Cache] HIT for {tier}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        # Memory fallback
        if cache_key in self._memory_cache:
            logger.info(f"[Cache] Memory HIT for {tier}")
            return self._memory_cache[cache_key]
        
        logger.debug(f"[Cache] MISS for {tier}")
        return None
    
    async def set(
        self,
        tier: str,
        query_plan: dict,
        result: dict,
        hypothesis_hash: str,
    ) -> None:
        """캐시 저장"""
        cache_key = self._make_cache_key(tier, query_plan, hypothesis_hash)
        ttl = CACHE_TTL.get(tier, CACHE_TTL["rag"])
        
        redis = await self._get_redis()
        if redis:
            try:
                await redis.setex(cache_key, ttl, json.dumps(result))
                logger.info(f"[Cache] SET for {tier}, TTL={ttl}s")
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
        
        # Memory fallback (no TTL)
        self._memory_cache[cache_key] = result
        logger.info(f"[Cache] Memory SET for {tier}")
    
    async def invalidate(self, hypothesis_hash: str) -> None:
        """특정 가설의 모든 캐시 무효화"""
        redis = await self._get_redis()
        if redis:
            try:
                pattern = f"study_plan:cache:*{hypothesis_hash}*"
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
                    logger.info(f"[Cache] Invalidated {len(keys)} keys")
            except Exception as e:
                logger.warning(f"Redis invalidate failed: {e}")


# 싱글톤 인스턴스
cache_manager = SearchCacheManager()
