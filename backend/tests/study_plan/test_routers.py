"""Tests for Study Plan Agent v3 Decision Point routers.

Run with: pytest tests/study_plan/test_routers.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent.study_plan.routers import (
    DP1SearchRouter,
    DP2CritiqueRouter,
    DP3SynthesisRouter,
)
from app.services.agent.study_plan.search.types import (
    SearchTier,
    SearchObjective,
    DP1RouterInput,
    DP2RouterInput,
    DP3RouterInput,
)


# ─────────────────────────────────────────────────────────────
# DP2 Critique Router Tests (Synchronous - no LLM needed)
# ─────────────────────────────────────────────────────────────


class TestDP2CritiqueRouter:
    """DP2 Critique 전략 라우터 테스트"""

    def setup_method(self):
        self.router = DP2CritiqueRouter()

    def test_redesign_missing_controls(self):
        """필수 대조군 누락시 redesign"""
        input_data = DP2RouterInput(
            quality_score=0.6,
            missing_controls=["vehicle", "positive"],
            evidence_gaps=[],
            feasibility_conflicts=[],
            unclear_elements=[],
            search_budget_remaining=1,
            loop_count=0,
            previous_gaps_searched=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "redesign"
        assert "vehicle" in result.reason.lower() or "positive" in result.reason.lower()

    def test_search_for_controls_with_budget(self):
        """예산 있으면 search_for_controls"""
        input_data = DP2RouterInput(
            quality_score=0.7,
            missing_controls=[],
            evidence_gaps=["dosing protocol", "mechanism"],
            feasibility_conflicts=[],
            unclear_elements=[],
            search_budget_remaining=1,
            loop_count=0,
            previous_gaps_searched=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "search_for_controls"
        assert len(result.target_gaps) > 0

    def test_no_repeat_gap_search(self):
        """같은 gap 2회 검색 금지"""
        input_data = DP2RouterInput(
            quality_score=0.7,
            missing_controls=[],
            evidence_gaps=["dosing protocol"],
            feasibility_conflicts=[],
            unclear_elements=[],
            search_budget_remaining=1,
            loop_count=0,
            previous_gaps_searched=["dosing protocol"],  # 이미 검색함
        )

        result = self.router.route(input_data, "run_001")

        # 이미 검색한 gap이므로 search_for_controls가 아니거나 해당 gap 미포함
        if result.decision == "search_for_controls":
            assert "dosing protocol" not in result.target_gaps

    def test_ask_user_unclear_elements(self):
        """불명확한 요소면 ask_user"""
        input_data = DP2RouterInput(
            quality_score=0.7,
            missing_controls=[],
            evidence_gaps=[],
            feasibility_conflicts=[],
            unclear_elements=["animal model", "dosing schedule"],
            search_budget_remaining=0,
            loop_count=0,
            previous_gaps_searched=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "ask_user"
        assert len(result.user_questions) > 0
        assert len(result.user_questions) <= 3  # 최대 3개

    def test_accept_minor_issues_high_quality(self):
        """높은 품질이면 accept_minor_issues"""
        input_data = DP2RouterInput(
            quality_score=0.85,
            missing_controls=[],
            evidence_gaps=[],
            feasibility_conflicts=[],
            unclear_elements=[],
            search_budget_remaining=0,
            loop_count=0,
            previous_gaps_searched=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "accept_minor_issues"

    def test_redesign_feasibility_conflicts(self):
        """실현가능성 충돌시 redesign"""
        input_data = DP2RouterInput(
            quality_score=0.7,
            missing_controls=[],
            evidence_gaps=[],
            feasibility_conflicts=["budget exceeded", "timeline too short"],
            unclear_elements=[],
            search_budget_remaining=1,
            loop_count=0,
            previous_gaps_searched=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "redesign"

    def test_loop_limit_reached(self):
        """루프 제한 도달시 accept"""
        input_data = DP2RouterInput(
            quality_score=0.5,
            missing_controls=["vehicle"],
            evidence_gaps=["mechanism"],
            feasibility_conflicts=["budget"],
            unclear_elements=["model"],
            search_budget_remaining=1,
            loop_count=2,  # MAX_DP2_LOOPS = 2
            previous_gaps_searched=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "accept_minor_issues"
        assert "루프 제한" in result.reason

    def test_generate_search_query_plan(self):
        """쿼리 계획 생성 테스트"""
        plan = self.router.generate_search_query_plan(
            target_gaps=["vehicle control", "positive control"],
            hypothesis="EGFR T790M mutation causes resistance",
        )

        assert plan.primary_query != ""
        assert plan.objective == SearchObjective.PROTOCOL_CONTROLS  # control 관련


# ─────────────────────────────────────────────────────────────
# DP3 Synthesis Router Tests
# ─────────────────────────────────────────────────────────────


class TestDP3SynthesisRouter:
    """DP3 Plan A/B 분기 라우터 테스트"""

    def setup_method(self):
        self.router = DP3SynthesisRouter()

    def test_single_plan_high_quality(self):
        """고품질 + 승인불필요 + 충분한 근거 = single_plan"""
        input_data = DP3RouterInput(
            quality_score=0.85,
            approval_required=False,
            web_limit_exceeded=False,
            evidence_sufficient=True,
            high_cost_experiment=False,
            ethics_required=False,
            explicit_constraints=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "single_plan"

    def test_plan_a_b_approval_required(self):
        """승인 필요시 plan_a_b"""
        input_data = DP3RouterInput(
            quality_score=0.85,
            approval_required=True,
            web_limit_exceeded=False,
            evidence_sufficient=True,
            high_cost_experiment=False,
            ethics_required=False,
            explicit_constraints=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "plan_a_b"

    def test_plan_a_b_high_cost(self):
        """고비용 실험시 plan_a_b"""
        input_data = DP3RouterInput(
            quality_score=0.85,
            approval_required=False,
            web_limit_exceeded=False,
            evidence_sufficient=True,
            high_cost_experiment=True,
            ethics_required=False,
            explicit_constraints=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "plan_a_b"

    def test_plan_a_b_ethics_required(self):
        """윤리 검토 필요시 plan_a_b"""
        input_data = DP3RouterInput(
            quality_score=0.85,
            approval_required=False,
            web_limit_exceeded=False,
            evidence_sufficient=True,
            high_cost_experiment=False,
            ethics_required=True,
            explicit_constraints=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "plan_a_b"

    def test_plan_b_only_web_limit_exceeded(self):
        """Web 한도 초과 + 근거 부족 = plan_b_only"""
        input_data = DP3RouterInput(
            quality_score=0.6,
            approval_required=False,
            web_limit_exceeded=True,
            evidence_sufficient=False,
            high_cost_experiment=False,
            ethics_required=False,
            explicit_constraints=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "plan_b_only"

    def test_plan_b_only_explicit_constraints(self):
        """명시적 제약 조건 있으면 plan_b_only"""
        input_data = DP3RouterInput(
            quality_score=0.85,
            approval_required=False,
            web_limit_exceeded=False,
            evidence_sufficient=True,
            high_cost_experiment=False,
            ethics_required=False,
            explicit_constraints=["budget limited", "timeline short"],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "plan_b_only"

    def test_get_plan_prompts_single(self):
        """single_plan 프롬프트 생성"""
        prompts = self.router.get_plan_prompts(
            decision="single_plan",
            plan_config={"focus": "optimal"},
        )

        assert "plan" in prompts
        assert prompts["plan"] != ""

    def test_get_plan_prompts_ab(self):
        """plan_a_b 프롬프트 생성"""
        prompts = self.router.get_plan_prompts(
            decision="plan_a_b",
            plan_config={"plan_a_focus": "optimal_design", "plan_b_focus": "practical"},
        )

        assert "plan_a" in prompts
        assert "plan_b" in prompts
        assert prompts["plan_a"] != ""
        assert prompts["plan_b"] != ""

    def test_get_plan_prompts_b_only(self):
        """plan_b_only 프롬프트 생성"""
        prompts = self.router.get_plan_prompts(
            decision="plan_b_only",
            plan_config={"constraints": ["budget"], "constraint_type": "explicit"},
        )

        assert "plan_b" in prompts
        assert prompts["plan_b"] != ""

    def test_default_plan_a_b(self):
        """기본값: plan_a_b (안전한 선택)"""
        input_data = DP3RouterInput(
            quality_score=0.7,  # 충분하지 않은 품질
            approval_required=False,
            web_limit_exceeded=False,
            evidence_sufficient=True,
            high_cost_experiment=False,
            ethics_required=False,
            explicit_constraints=[],
        )

        result = self.router.route(input_data, "run_001")

        assert result.decision == "plan_a_b"


# ─────────────────────────────────────────────────────────────
# DP1 Search Router Tests (Async - needs LLM mocking)
# ─────────────────────────────────────────────────────────────


class TestDP1SearchRouter:
    """DP1 검색 승격 라우터 테스트 (LLM Mocked)"""

    def setup_method(self):
        self.mock_llm = MagicMock()
        self.router = DP1SearchRouter(llm=self.mock_llm)

    @pytest.mark.asyncio
    async def test_proceed_with_high_coverage_rag(self):
        """높은 RAG coverage에서 proceed 결정"""
        input_data = DP1RouterInput(
            current_tier=SearchTier.RAG,
            coverage_score=0.85,
            evidence_density=3,
            test_questions=["q1", "q2"],
            answered_questions=["q1", "q2"],
            epmc_budget_remaining=2,
            web_budget_remaining=1,
        )

        result = await self.router.route(input_data, "hypothesis text", "run_001")

        assert result.decision == "proceed"

    @pytest.mark.asyncio
    async def test_upgrade_to_epmc_low_coverage(self):
        """낮은 RAG coverage에서 EPMC 승격"""
        # LLM mock 설정
        mock_response = MagicMock()
        mock_response.content = '{"objective": "mechanism", "primary_query": "test query", "fallback_queries": [], "filters": {}}'
        self.mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        input_data = DP1RouterInput(
            current_tier=SearchTier.RAG,
            coverage_score=0.60,
            evidence_density=1,
            test_questions=["q1", "q2"],
            answered_questions=["q1"],
            epmc_budget_remaining=2,
            web_budget_remaining=1,
        )

        result = await self.router.route(input_data, "EGFR mutation hypothesis", "run_001")

        assert result.decision == "upgrade_to_epmc"
        assert result.next_tier == SearchTier.EPMC
        assert result.query_plan is not None

    @pytest.mark.asyncio
    async def test_upgrade_to_web_from_epmc(self):
        """EPMC에서 Web으로 승격"""
        mock_response = MagicMock()
        mock_response.content = '{"objective": "evidence_strength", "primary_query": "test", "fallback_queries": [], "filters": {}}'
        self.mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        input_data = DP1RouterInput(
            current_tier=SearchTier.EPMC,
            coverage_score=0.65,
            evidence_density=2,
            test_questions=["q1", "q2", "q3", "q4"],
            answered_questions=["q1"],  # 25% 응답률
            epmc_budget_remaining=0,
            web_budget_remaining=1,
        )

        result = await self.router.route(input_data, "hypothesis", "run_001")

        assert result.decision == "upgrade_to_web"
        assert result.next_tier == SearchTier.WEB

    @pytest.mark.asyncio
    async def test_skip_web_limit_no_budget(self):
        """Web 예산 없으면 skip_web_limit"""
        input_data = DP1RouterInput(
            current_tier=SearchTier.EPMC,
            coverage_score=0.60,
            evidence_density=1,
            test_questions=["q1", "q2", "q3", "q4"],
            answered_questions=["q1"],
            epmc_budget_remaining=0,
            web_budget_remaining=0,
        )

        result = await self.router.route(input_data, "hypothesis", "run_001")

        assert result.decision == "skip_web_limit"

    @pytest.mark.asyncio
    async def test_proceed_after_web(self):
        """Web 검색 후 항상 proceed"""
        input_data = DP1RouterInput(
            current_tier=SearchTier.WEB,
            coverage_score=0.50,  # 낮아도 proceed
            evidence_density=1,
            test_questions=["q1", "q2"],
            answered_questions=[],
            epmc_budget_remaining=0,
            web_budget_remaining=0,
        )

        result = await self.router.route(input_data, "hypothesis", "run_001")

        assert result.decision == "proceed"
