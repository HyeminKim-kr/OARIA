"""Search Cache Manager - 검색 결과 캐싱

Redis 기반 검색 결과 캐시:
- 티어별 TTL 차등 적용
- 가설 해시 기반 캐시 키

TTL 정책:
- RAG: 7일 (내부 데이터, 자주 변경)
- EPMC: 30일 (외부 API, 느린 갱신)
- Web: 7일 (웹 컨텐츠, 빠른 변화)
"""

import json
import logging
import hashlib
from typing import Optional, Any

import redis.asyncio as aioredis

from app.config import settings
from .types import SearchTier, EvidenceSnippetV3

logger = logging.getLogger(__name__)

# Redis 키 프리픽스
CACHE_PREFIX = "study_plan:cache"

# 티어별 TTL (초)
CACHE_TTL = {
    SearchTier.RAG: 7 * 24 * 60 * 60,  # 7일
    SearchTier.EPMC: 30 * 24 * 60 * 60,  # 30일
    SearchTier.WEB: 7 * 24 * 60 * 60,  # 7일
}


class SearchCacheManager:
    """검색 결과 캐시 관리자

    캐시 키 구조:
    - {CACHE_PREFIX}:{tier}:{hypothesis_hash}:{query_hash}
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def _ensure_redis(self) -> aioredis.Redis:
        """Redis 연결 지연 초기화"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _hash_hypothesis(self, hypothesis: str) -> str:
        """가설 해시 생성 (캐시 키용)"""
        return hashlib.md5(hypothesis.strip().lower().encode()).hexdigest()[:16]

    def _hash_query(self, query: str | dict) -> str:
        """쿼리 해시 생성"""
        if isinstance(query, dict):
            query_str = json.dumps(query, sort_keys=True)
        else:
            query_str = query.strip().lower()
        return hashlib.md5(query_str.encode()).hexdigest()[:16]

    def _cache_key(
        self,
        tier: SearchTier,
        hypothesis_hash: str,
        query_hash: str,
    ) -> str:
        """캐시 키 생성"""
        tier_name = tier.name.lower()
        return f"{CACHE_PREFIX}:{tier_name}:{hypothesis_hash}:{query_hash}"

    async def get(
        self,
        tier: SearchTier,
        query: str | dict,
        hypothesis: str,
    ) -> list[EvidenceSnippetV3] | None:
        """캐시에서 검색 결과 조회

        Args:
            tier: 검색 티어
            query: 검색 쿼리 (문자열 또는 QueryPlan dict)
            hypothesis: 원본 가설 (해시용)

        Returns:
            캐시된 결과 또는 None
        """
        redis = await self._ensure_redis()

        hypothesis_hash = self._hash_hypothesis(hypothesis)
        query_hash = self._hash_query(query)
        key = self._cache_key(tier, hypothesis_hash, query_hash)

        try:
            cached = await redis.get(key)
            if cached is None:
                return None

            data = json.loads(cached)
            snippets = [EvidenceSnippetV3.from_dict(s) for s in data["snippets"]]

            logger.info(
                "cache_hit tier=%s key=%s count=%d",
                tier.name,
                key[-32:],
                len(snippets),
            )
            return snippets

        except Exception as e:
            logger.warning("cache_get_error key=%s error=%s", key[-32:], str(e))
            return None

    async def set(
        self,
        tier: SearchTier,
        query: str | dict,
        hypothesis: str,
        snippets: list[EvidenceSnippetV3],
    ) -> None:
        """검색 결과 캐시 저장

        Args:
            tier: 검색 티어
            query: 검색 쿼리
            hypothesis: 원본 가설
            snippets: 저장할 스니펫 목록
        """
        redis = await self._ensure_redis()

        hypothesis_hash = self._hash_hypothesis(hypothesis)
        query_hash = self._hash_query(query)
        key = self._cache_key(tier, hypothesis_hash, query_hash)
        ttl = CACHE_TTL.get(tier, 7 * 24 * 60 * 60)

        try:
            data = {
                "tier": tier.value,
                "query_hash": query_hash,
                "hypothesis_hash": hypothesis_hash,
                "snippet_count": len(snippets),
                "snippets": [s.to_dict() for s in snippets],
            }

            await redis.set(key, json.dumps(data), ex=ttl)

            logger.info(
                "cache_set tier=%s key=%s count=%d ttl=%d",
                tier.name,
                key[-32:],
                len(snippets),
                ttl,
            )

        except Exception as e:
            logger.warning("cache_set_error key=%s error=%s", key[-32:], str(e))

    async def invalidate(
        self,
        tier: SearchTier | None = None,
        hypothesis: str | None = None,
    ) -> int:
        """캐시 무효화

        Args:
            tier: 특정 티어만 무효화 (None이면 전체)
            hypothesis: 특정 가설 관련만 무효화 (None이면 전체)

        Returns:
            삭제된 키 수
        """
        redis = await self._ensure_redis()

        # 패턴 생성
        if tier and hypothesis:
            hypothesis_hash = self._hash_hypothesis(hypothesis)
            pattern = f"{CACHE_PREFIX}:{tier.name.lower()}:{hypothesis_hash}:*"
        elif tier:
            pattern = f"{CACHE_PREFIX}:{tier.name.lower()}:*"
        elif hypothesis:
            hypothesis_hash = self._hash_hypothesis(hypothesis)
            pattern = f"{CACHE_PREFIX}:*:{hypothesis_hash}:*"
        else:
            pattern = f"{CACHE_PREFIX}:*"

        try:
            keys = []
            async for key in redis.scan_iter(pattern):
                keys.append(key)

            if keys:
                deleted = await redis.delete(*keys)
                logger.info(
                    "cache_invalidate pattern=%s deleted=%d",
                    pattern,
                    deleted,
                )
                return deleted
            return 0

        except Exception as e:
            logger.warning("cache_invalidate_error pattern=%s error=%s", pattern, str(e))
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """캐시 통계 조회

        Returns:
            티어별 캐시 키 수
        """
        redis = await self._ensure_redis()

        stats = {
            "rag": 0,
            "epmc": 0,
            "web": 0,
            "total": 0,
        }

        try:
            for tier in SearchTier:
                pattern = f"{CACHE_PREFIX}:{tier.name.lower()}:*"
                count = 0
                async for _ in redis.scan_iter(pattern):
                    count += 1
                stats[tier.name.lower()] = count
                stats["total"] += count

            return stats

        except Exception as e:
            logger.warning("cache_stats_error error=%s", str(e))
            return stats

    async def close(self):
        """Redis 연결 종료"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 싱글톤 인스턴스
cache_manager = SearchCacheManager()
