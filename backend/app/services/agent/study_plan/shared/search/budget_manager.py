"""Search Budget Manager

v3 검색 예산 관리.
- Run별 검색 횟수 제한
- 월간 Web 검색 제한
- Redis 기반 상태 추적
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# 예산 제한 상수
MAX_WEB_CALLS_PER_RUN = settings.search_web_per_run_limit
MAX_EPMC_CALLS_PER_RUN = settings.search_epmc_per_run_limit
WEB_MONTHLY_LIMIT = settings.search_web_monthly_limit


@dataclass
class RunBudget:
    """단일 실행의 예산 상태"""
    run_id: str
    epmc_count: int = 0
    web_count: int = 0
    
    @property
    def can_use_epmc(self) -> bool:
        return self.epmc_count < MAX_EPMC_CALLS_PER_RUN
    
    @property
    def can_use_web(self) -> bool:
        return self.web_count < MAX_WEB_CALLS_PER_RUN
    
    @property
    def epmc_remaining(self) -> int:
        return max(0, MAX_EPMC_CALLS_PER_RUN - self.epmc_count)
    
    @property
    def web_remaining(self) -> int:
        return max(0, MAX_WEB_CALLS_PER_RUN - self.web_count)


class SearchBudgetManager:
    """
    검색 예산 관리자
    
    Redis를 사용하여:
    - Run별 검색 횟수 추적
    - 월간 Web 검색 횟수 추적
    
    Redis 없이도 동작 (인메모리 fallback)
    """
    
    def __init__(self):
        self._run_budgets: dict[str, RunBudget] = {}
        self._web_monthly_count: int = 0
        self._redis_client = None
        self._redis_available = False
        
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
                logger.info("Redis connected for budget management")
            except Exception as e:
                logger.warning(f"Redis not available, using in-memory budget: {e}")
                self._redis_available = False
        return self._redis_client if self._redis_available else None
    
    def init_run(self, run_id: str) -> RunBudget:
        """새 실행 예산 초기화"""
        budget = RunBudget(run_id=run_id)
        self._run_budgets[run_id] = budget
        logger.info(f"[Budget] Initialized run {run_id}")
        return budget
    
    def get_run_budget(self, run_id: str) -> RunBudget:
        """실행 예산 조회 (없으면 생성)"""
        if run_id not in self._run_budgets:
            return self.init_run(run_id)
        return self._run_budgets[run_id]
    
    async def can_use_web(self, run_id: str) -> bool:
        """Web 검색 가능 여부"""
        budget = self.get_run_budget(run_id)
        if not budget.can_use_web:
            return False
        
        # 월간 제한 체크
        monthly_remaining = await self.get_web_monthly_remaining()
        return monthly_remaining > 0
    
    async def can_use_epmc(self, run_id: str) -> bool:
        """EPMC 검색 가능 여부"""
        budget = self.get_run_budget(run_id)
        return budget.can_use_epmc
    
    def increment_epmc(self, run_id: str) -> None:
        """EPMC 검색 횟수 증가"""
        budget = self.get_run_budget(run_id)
        budget.epmc_count += 1
        logger.info(f"[Budget] EPMC count for {run_id}: {budget.epmc_count}")
    
    async def increment_web(self, run_id: str) -> None:
        """Web 검색 횟수 증가 (run + monthly)"""
        budget = self.get_run_budget(run_id)
        budget.web_count += 1
        await self._increment_web_monthly()
        logger.info(f"[Budget] Web count for {run_id}: {budget.web_count}")
    
    async def get_web_monthly_remaining(self) -> int:
        """월간 Web 검색 잔여 횟수"""
        redis = await self._get_redis()
        if redis:
            try:
                count = await redis.get("study_plan:web_monthly_count")
                current = int(count) if count else 0
                return max(0, WEB_MONTHLY_LIMIT - current)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
        
        return max(0, WEB_MONTHLY_LIMIT - self._web_monthly_count)
    
    async def _increment_web_monthly(self) -> None:
        """월간 Web 검색 횟수 증가"""
        redis = await self._get_redis()
        if redis:
            try:
                # 월 단위로 키 만료 설정 (30일)
                await redis.incr("study_plan:web_monthly_count")
                await redis.expire("study_plan:web_monthly_count", 30 * 24 * 3600)
                return
            except Exception as e:
                logger.warning(f"Redis incr failed: {e}")
        
        self._web_monthly_count += 1
    
    def cleanup_run(self, run_id: str) -> None:
        """실행 완료 후 정리"""
        if run_id in self._run_budgets:
            del self._run_budgets[run_id]
            logger.info(f"[Budget] Cleaned up run {run_id}")


# 싱글톤 인스턴스
budget_manager = SearchBudgetManager()
