"""DP1 Search Router - 검색 승격 결정

검색 결과를 평가하여 다음 티어로 승격할지 결정

승격 규칙:
- RAG → EPMC: coverage < 0.70 OR evidence_density < 2
- EPMC → Web: coverage < 0.75 AND 핵심 질문 빈약 AND web_budget > 0
- Web budget 없으면: skip_web_limit → Plan B
"""

import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from ..search.types import (
    SearchTier,
    SearchObjective,
    QueryPlan,
    DP1RouterInput,
    DP1RouterOutput,
    DP1Decision,
)
from ..search.budget_manager import budget_manager

logger = logging.getLogger(__name__)

# 승격 임계값
COVERAGE_THRESHOLD_RAG_TO_EPMC = 0.70
EVIDENCE_DENSITY_THRESHOLD = 2
COVERAGE_THRESHOLD_EPMC_TO_WEB = 0.75
MIN_ANSWERED_RATIO = 0.5


class QueryPlanOutput(BaseModel):
    """LLM이 생성하는 쿼리 계획"""

    objective: str = Field(
        description="검색 목적: mechanism, protocol_controls, evidence_strength"
    )
    primary_query: str = Field(description="주요 검색 쿼리")
    fallback_queries: list[str] = Field(
        default_factory=list, description="대체 검색 쿼리 (최대 2개)"
    )
    filters: dict = Field(
        default_factory=dict, description="검색 필터 (year_from, open_access_only)"
    )


class DP1SearchRouter:
    """DP1 검색 승격 라우터

    현재 검색 결과를 분석하여 다음 행동 결정:
    - proceed: 현재 결과로 진행
    - upgrade_to_epmc: EPMC로 승격
    - upgrade_to_web: Web으로 승격
    - skip_web_limit: Web 예산 초과로 Plan B 방향
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def route(
        self,
        input_data: DP1RouterInput,
        hypothesis: str,
        run_id: str,
    ) -> DP1RouterOutput:
        """검색 승격 결정

        Args:
            input_data: 현재 검색 상태
            hypothesis: 원본 가설 (쿼리 생성용)
            run_id: 실행 ID

        Returns:
            DP1RouterOutput: 결정 및 다음 쿼리 계획
        """
        tier = input_data.current_tier
        coverage = input_data.coverage_score
        density = input_data.evidence_density

        # 1. RAG 결과 평가 → EPMC 승격 여부
        if tier == SearchTier.RAG:
            if coverage < COVERAGE_THRESHOLD_RAG_TO_EPMC or density < EVIDENCE_DENSITY_THRESHOLD:
                # EPMC 예산 확인
                if input_data.epmc_budget_remaining > 0:
                    query_plan = await self._generate_query_plan(
                        hypothesis=hypothesis,
                        objective=SearchObjective.MECHANISM,
                        context=f"RAG coverage: {coverage:.2f}, density: {density}",
                    )
                    logger.info(
                        "dp1_upgrade_to_epmc run_id=%s coverage=%.2f density=%d",
                        run_id,
                        coverage,
                        density,
                    )
                    return DP1RouterOutput(
                        decision="upgrade_to_epmc",
                        reason=f"RAG 커버리지 부족 (coverage={coverage:.2f}, density={density})",
                        next_tier=SearchTier.EPMC,
                        objective=SearchObjective.MECHANISM,
                        query_plan=query_plan,
                    )
                else:
                    logger.warning("dp1_epmc_budget_exhausted run_id=%s", run_id)

            # 충분하면 진행
            logger.info(
                "dp1_proceed_rag run_id=%s coverage=%.2f density=%d",
                run_id,
                coverage,
                density,
            )
            return DP1RouterOutput(
                decision="proceed",
                reason=f"RAG 결과 충분 (coverage={coverage:.2f})",
            )

        # 2. EPMC 결과 평가 → Web 승격 여부
        elif tier == SearchTier.EPMC:
            # 핵심 질문 응답률 계산
            answered_ratio = self._calculate_answered_ratio(
                input_data.test_questions,
                input_data.answered_questions,
            )

            if coverage < COVERAGE_THRESHOLD_EPMC_TO_WEB and answered_ratio < MIN_ANSWERED_RATIO:
                if input_data.web_budget_remaining > 0:
                    # 가장 부족한 영역 식별
                    objective = self._identify_gap_objective(
                        input_data.test_questions,
                        input_data.answered_questions,
                    )
                    query_plan = await self._generate_query_plan(
                        hypothesis=hypothesis,
                        objective=objective,
                        context=f"EPMC coverage: {coverage:.2f}, answered: {answered_ratio:.0%}",
                    )
                    logger.info(
                        "dp1_upgrade_to_web run_id=%s coverage=%.2f answered=%.0f%%",
                        run_id,
                        coverage,
                        answered_ratio * 100,
                    )
                    return DP1RouterOutput(
                        decision="upgrade_to_web",
                        reason=f"EPMC 커버리지 부족 (coverage={coverage:.2f}, 응답률={answered_ratio:.0%})",
                        next_tier=SearchTier.WEB,
                        objective=objective,
                        query_plan=query_plan,
                    )
                else:
                    # Web 예산 없음 → Plan B 방향
                    logger.warning(
                        "dp1_skip_web_limit run_id=%s coverage=%.2f",
                        run_id,
                        coverage,
                    )
                    return DP1RouterOutput(
                        decision="skip_web_limit",
                        reason="Web 검색 예산 초과 - Plan B 방향으로 진행",
                    )

            # 충분하면 진행
            logger.info(
                "dp1_proceed_epmc run_id=%s coverage=%.2f answered=%.0f%%",
                run_id,
                coverage,
                answered_ratio * 100,
            )
            return DP1RouterOutput(
                decision="proceed",
                reason=f"EPMC 결과 충분 (coverage={coverage:.2f})",
            )

        # 3. Web 이후 → 항상 진행
        logger.info("dp1_proceed_web run_id=%s coverage=%.2f", run_id, coverage)
        return DP1RouterOutput(
            decision="proceed",
            reason="최종 티어 검색 완료",
        )

    async def _generate_query_plan(
        self,
        hypothesis: str,
        objective: SearchObjective,
        context: str,
    ) -> QueryPlan:
        """LLM을 사용하여 검색 쿼리 계획 생성"""
        prompt = f"""다음 가설에 대한 {objective.value} 검색 쿼리를 생성하세요.

가설: {hypothesis}

현재 상황: {context}

검색 목적:
- mechanism: 가설을 뒷받침하는 기전 연구
- protocol_controls: 실험 프로토콜, 대조군 정보
- evidence_strength: 근거 강도, 재현성

JSON 형식으로 응답:
{{
  "objective": "{objective.value}",
  "primary_query": "주요 검색 쿼리 (영문)",
  "fallback_queries": ["대체 쿼리 1", "대체 쿼리 2"],
  "filters": {{"year_from": 2018, "open_access_only": true}}
}}"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="당신은 생의학 연구 검색 전문가입니다."),
                HumanMessage(content=prompt),
            ])

            # JSON 파싱
            import json
            import re

            content = response.content
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return QueryPlan(
                    objective=SearchObjective(data.get("objective", objective.value)),
                    primary_query=data.get("primary_query", hypothesis[:100]),
                    fallback_queries=data.get("fallback_queries", [])[:2],
                    filters=data.get("filters", {"year_from": 2018, "open_access_only": True}),
                )

        except Exception as e:
            logger.warning("query_plan_generation_error error=%s", str(e))

        # 폴백: 단순 쿼리
        return QueryPlan(
            objective=objective,
            primary_query=hypothesis[:100],
            fallback_queries=[],
            filters={"year_from": 2018, "open_access_only": True},
        )

    def _calculate_answered_ratio(
        self,
        test_questions: list[str],
        answered_questions: list[str],
    ) -> float:
        """핵심 질문 응답률 계산"""
        if not test_questions:
            return 1.0
        return len(answered_questions) / len(test_questions)

    def _identify_gap_objective(
        self,
        test_questions: list[str],
        answered_questions: list[str],
    ) -> SearchObjective:
        """미응답 질문 기반 검색 목적 결정"""
        unanswered = set(test_questions) - set(answered_questions)

        # 키워드 기반 분류
        mechanism_keywords = ["mechanism", "pathway", "how", "why", "cause"]
        protocol_keywords = ["protocol", "method", "control", "dose", "treatment"]

        for q in unanswered:
            q_lower = q.lower()
            if any(kw in q_lower for kw in mechanism_keywords):
                return SearchObjective.MECHANISM
            if any(kw in q_lower for kw in protocol_keywords):
                return SearchObjective.PROTOCOL_CONTROLS

        return SearchObjective.EVIDENCE_STRENGTH
