"""Search Budget Manager - API 사용량 관리

Redis 기반 예산 관리:
- run당 호출 횟수 제한
- 월간 사용량 추적 (Tavily)
- 캐시 TTL 관리

가드레일:
- Tavily Web: run당 1회, 월 1,000회
- Europe PMC: run당 2회
"""

import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings
from .types import SearchTier

logger = logging.getLogger(__name__)

# Redis 키 프리픽스
BUDGET_PREFIX = "study_plan:budget"
RUN_PREFIX = f"{BUDGET_PREFIX}:run"
MONTHLY_PREFIX = f"{BUDGET_PREFIX}:monthly"


class SearchBudgetManager:
    """검색 예산 관리자

    Redis를 사용한 사용량 추적:
    - run:{run_id}:web - run당 Web 호출 횟수
    - run:{run_id}:epmc - run당 EPMC 호출 횟수
    - monthly:web:{YYYY-MM} - 월간 Web 호출 횟수
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

    def _run_key(self, run_id: str, tier: SearchTier) -> str:
        """run당 카운터 키"""
        tier_name = "web" if tier == SearchTier.WEB else "epmc"
        return f"{RUN_PREFIX}:{run_id}:{tier_name}"

    def _monthly_key(self) -> str:
        """월간 카운터 키 (Tavily Web용)"""
        month = datetime.now().strftime("%Y-%m")
        return f"{MONTHLY_PREFIX}:web:{month}"

    async def init_run(self, run_id: str) -> None:
        """run 시작 시 예산 초기화

        Args:
            run_id: 실행 ID
        """
        redis = await self._ensure_redis()

        # run당 카운터 초기화 (1시간 TTL)
        web_key = self._run_key(run_id, SearchTier.WEB)
        epmc_key = self._run_key(run_id, SearchTier.EPMC)

        await redis.set(web_key, 0, ex=3600)
        await redis.set(epmc_key, 0, ex=3600)

        logger.info("budget_init run_id=%s", run_id)

    async def get_run_count(self, run_id: str, tier: SearchTier) -> int:
        """run당 호출 횟수 조회

        Args:
            run_id: 실행 ID
            tier: 검색 티어

        Returns:
            현재 호출 횟수
        """
        redis = await self._ensure_redis()
        key = self._run_key(run_id, tier)
        count = await redis.get(key)
        return int(count) if count else 0

    async def increment_run(self, run_id: str, tier: SearchTier) -> int:
        """run당 호출 횟수 증가

        Args:
            run_id: 실행 ID
            tier: 검색 티어

        Returns:
            증가 후 횟수
        """
        redis = await self._ensure_redis()
        key = self._run_key(run_id, tier)
        count = await redis.incr(key)

        # Web 검색은 월간 카운터도 증가
        if tier == SearchTier.WEB:
            await redis.incr(self._monthly_key())

        logger.info(
            "budget_increment run_id=%s tier=%s count=%d",
            run_id,
            tier.name,
            count,
        )
        return count

    async def can_use_tier(self, run_id: str, tier: SearchTier) -> bool:
        """티어 사용 가능 여부

        Args:
            run_id: 실행 ID
            tier: 검색 티어

        Returns:
            사용 가능 여부
        """
        current_count = await self.get_run_count(run_id, tier)

        if tier == SearchTier.WEB:
            # run당 + 월간 제한 모두 체크
            if current_count >= settings.search_web_per_run_limit:
                return False
            monthly_remaining = await self.get_web_monthly_remaining()
            return monthly_remaining > 0

        elif tier == SearchTier.EPMC:
            return current_count < settings.search_epmc_per_run_limit

        # RAG는 제한 없음
        return True

    async def get_remaining(self, run_id: str, tier: SearchTier) -> int:
        """남은 호출 횟수

        Args:
            run_id: 실행 ID
            tier: 검색 티어

        Returns:
            남은 횟수
        """
        current_count = await self.get_run_count(run_id, tier)

        if tier == SearchTier.WEB:
            run_remaining = settings.search_web_per_run_limit - current_count
            monthly_remaining = await self.get_web_monthly_remaining()
            return min(run_remaining, monthly_remaining)

        elif tier == SearchTier.EPMC:
            return settings.search_epmc_per_run_limit - current_count

        # RAG는 무제한
        return 999

    async def get_web_monthly_remaining(self) -> int:
        """Tavily Web 월간 남은 횟수

        Returns:
            월간 남은 호출 횟수
        """
        redis = await self._ensure_redis()
        key = self._monthly_key()
        count = await redis.get(key)
        current = int(count) if count else 0
        return max(0, settings.search_web_monthly_limit - current)

    async def get_web_monthly_used(self) -> int:
        """Tavily Web 월간 사용량

        Returns:
            월간 사용 횟수
        """
        redis = await self._ensure_redis()
        key = self._monthly_key()
        count = await redis.get(key)
        return int(count) if count else 0

    async def get_budget_status(self, run_id: str) -> dict:
        """전체 예산 상태 조회

        Args:
            run_id: 실행 ID

        Returns:
            예산 상태 딕셔너리
        """
        web_count = await self.get_run_count(run_id, SearchTier.WEB)
        epmc_count = await self.get_run_count(run_id, SearchTier.EPMC)
        web_monthly = await self.get_web_monthly_used()

        return {
            "run_id": run_id,
            "web": {
                "run_used": web_count,
                "run_limit": settings.search_web_per_run_limit,
                "run_remaining": settings.search_web_per_run_limit - web_count,
                "monthly_used": web_monthly,
                "monthly_limit": settings.search_web_monthly_limit,
                "monthly_remaining": settings.search_web_monthly_limit - web_monthly,
            },
            "epmc": {
                "run_used": epmc_count,
                "run_limit": settings.search_epmc_per_run_limit,
                "run_remaining": settings.search_epmc_per_run_limit - epmc_count,
            },
        }

    async def close(self):
        """Redis 연결 종료"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 싱글톤 인스턴스
budget_manager = SearchBudgetManager()
