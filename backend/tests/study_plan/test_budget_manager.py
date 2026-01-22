"""Tests for Study Plan Agent v3 Budget Manager.

Run with: pytest tests/study_plan/test_budget_manager.py -v

Note: These tests mock Redis to run without external dependencies.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.agent.study_plan.search.types import SearchTier


# ─────────────────────────────────────────────────────────────
# Budget Manager Tests (Mocked)
# ─────────────────────────────────────────────────────────────


class TestBudgetManager:
    """예산 관리자 테스트 (Redis Mocked)"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.incr = AsyncMock(return_value=1)
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_init_run(self, mock_redis):
        """run 초기화 테스트"""
        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            await budget_manager.init_run("run_test_001")

            # set이 호출되었는지 확인 (web, epmc 각각)
            assert mock_redis.set.call_count >= 2

    @pytest.mark.asyncio
    async def test_can_use_tier_rag_always_true(self, mock_redis):
        """RAG tier는 항상 사용 가능"""
        mock_redis.get = AsyncMock(return_value="0")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            result = await budget_manager.can_use_tier("run_001", SearchTier.RAG)

            # RAG는 항상 True
            assert result is True

    @pytest.mark.asyncio
    async def test_can_use_tier_epmc_with_budget(self, mock_redis):
        """EPMC 예산 있을 때 사용 가능"""
        # run당 0회 사용 상태
        mock_redis.get = AsyncMock(return_value="0")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            result = await budget_manager.can_use_tier("run_001", SearchTier.EPMC)

            assert result is True

    @pytest.mark.asyncio
    async def test_can_use_tier_epmc_exhausted(self, mock_redis):
        """EPMC 예산 소진시 사용 불가"""
        # run당 2회 사용 (limit = 2)
        mock_redis.get = AsyncMock(return_value="2")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            result = await budget_manager.can_use_tier("run_001", SearchTier.EPMC)

            assert result is False

    @pytest.mark.asyncio
    async def test_can_use_tier_web_monthly_limit(self, mock_redis):
        """Web 월간 한도 체크"""
        # run당 0회, 월간 1000회 사용 (limit = 1000)
        mock_redis.get = AsyncMock(return_value="1000")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            result = await budget_manager.can_use_tier("run_001", SearchTier.WEB)

            assert result is False

    @pytest.mark.asyncio
    async def test_increment_run(self, mock_redis):
        """사용량 증가 테스트"""
        mock_redis.incr = AsyncMock(return_value=1)

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            count = await budget_manager.increment_run("run_001", SearchTier.EPMC)

            mock_redis.incr.assert_called()
            assert count == 1

    @pytest.mark.asyncio
    async def test_get_remaining(self, mock_redis):
        """남은 예산 조회"""
        mock_redis.get = AsyncMock(return_value="1")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            remaining = await budget_manager.get_remaining("run_001", SearchTier.EPMC)

            # EPMC limit = 2, used = 1, remaining = 1
            assert remaining == 1

    @pytest.mark.asyncio
    async def test_get_web_monthly_remaining(self, mock_redis):
        """Web 월간 남은 횟수 조회"""
        mock_redis.get = AsyncMock(return_value="500")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            remaining = await budget_manager.get_web_monthly_remaining()

            # Monthly limit = 1000, used = 500
            assert remaining == 500

    @pytest.mark.asyncio
    async def test_get_budget_status(self, mock_redis):
        """전체 예산 상태 조회"""
        mock_redis.get = AsyncMock(return_value="0")

        with patch(
            "app.services.agent.study_plan.search.budget_manager.budget_manager._redis",
            mock_redis,
        ):
            from app.services.agent.study_plan.search.budget_manager import budget_manager

            status = await budget_manager.get_budget_status("run_001")

            assert "run_id" in status
            assert "web" in status
            assert "epmc" in status
            assert status["web"]["run_limit"] == 1
            assert status["epmc"]["run_limit"] == 2


# ─────────────────────────────────────────────────────────────
# Budget Manager Integration Tests
# ─────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Requires running Redis")
class TestBudgetManagerIntegration:
    """실제 Redis 연동 테스트 (로컬 개발용)"""

    @pytest.mark.asyncio
    async def test_full_run_lifecycle(self):
        """전체 run 라이프사이클 테스트"""
        from app.services.agent.study_plan.search.budget_manager import budget_manager

        run_id = "test_run_integration"

        # 1. 초기화
        await budget_manager.init_run(run_id)

        # 2. RAG 사용
        assert await budget_manager.can_use_tier(run_id, SearchTier.RAG) is True

        # 3. EPMC 2회 사용
        assert await budget_manager.can_use_tier(run_id, SearchTier.EPMC) is True
        await budget_manager.increment_run(run_id, SearchTier.EPMC)

        assert await budget_manager.can_use_tier(run_id, SearchTier.EPMC) is True
        await budget_manager.increment_run(run_id, SearchTier.EPMC)

        # 4. EPMC 3회째는 불가
        assert await budget_manager.can_use_tier(run_id, SearchTier.EPMC) is False

        # 5. Web 사용
        assert await budget_manager.can_use_tier(run_id, SearchTier.WEB) is True
        await budget_manager.increment_run(run_id, SearchTier.WEB)

        # 6. Web 2회째는 불가
        assert await budget_manager.can_use_tier(run_id, SearchTier.WEB) is False
