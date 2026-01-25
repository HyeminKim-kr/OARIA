"""DP2 Critique Router

Critique 후 전략 결정 라우터.

규칙 (우선순위 순):
1. missing_controls (vehicle/positive/rescue) → redesign
2. evidence_gaps + budget 있음 → search_for_controls (같은 gap 2회 금지)
3. feasibility_conflicts → redesign (Plan B 방향)
4. 모델/assay 불명확 → ask_user (최대 3개)
5. quality >= 0.8 + 하드실패 없음 → accept_minor_issues
"""

import logging
from typing import Optional

from ..search.types import DP2RouterInput, DP2RouterOutput

logger = logging.getLogger(__name__)


class DP2CritiqueRouter:
    """
    DP2: Critique 후 전략 결정 라우터
    
    Critic의 검토 결과를 분석하고 다음 행동을 결정합니다.
    """
    
    # 품질 임계값
    QUALITY_THRESHOLD = 0.80
    MAX_USER_QUESTIONS = 3
    MAX_LOOP_COUNT = 2
    
    # 필수 대조군 목록
    REQUIRED_CONTROLS = ["vehicle", "mock", "positive", "non_targeting"]
    
    def route(self, input_data: DP2RouterInput, run_id: str = "") -> DP2RouterOutput:
        """
        Critique 후 전략 결정
        
        Args:
            input_data: DP2RouterInput
            run_id: 실행 ID (로깅용)
            
        Returns:
            DP2RouterOutput: 결정 결과
        """
        logger.info(
            f"[DP2] run_id={run_id} quality={input_data.quality_score:.2f} "
            f"loop={input_data.dp2_loop_count} "
            f"missing_controls={input_data.missing_controls}"
        )
        
        # 루프 제한 체크
        if input_data.dp2_loop_count >= self.MAX_LOOP_COUNT:
            logger.info("[DP2] Loop limit reached, accepting with issues")
            return DP2RouterOutput(
                decision="accept_minor_issues",
                reason="Loop limit reached, accepting current design",
            )
        
        # 1. 필수 대조군 누락 → redesign
        missing_required = self._check_missing_required_controls(input_data.missing_controls)
        if missing_required:
            return DP2RouterOutput(
                decision="redesign",
                reason=f"Missing required controls: {', '.join(missing_required)}",
            )
        
        # 2. Evidence 갭 + 예산 있음 → search_for_controls
        #    (같은 gap 연속 검색 금지)
        searchable_gaps = self._get_searchable_gaps(
            input_data.evidence_gaps,
            input_data.previous_gaps_searched,
        )
        
        if searchable_gaps and self._has_search_budget(input_data):
            queries = self._generate_search_queries(searchable_gaps)
            return DP2RouterOutput(
                decision="search_for_controls",
                reason=f"Searching for evidence on: {', '.join(searchable_gaps[:2])}",
                search_queries=queries,
            )
        
        # 3. 실현가능성 충돌 → redesign (Plan B 방향)
        if input_data.feasibility_conflicts:
            return DP2RouterOutput(
                decision="redesign",
                reason=f"Feasibility conflicts: {', '.join(input_data.feasibility_conflicts[:2])}",
            )
        
        # 4. 불명확 항목 → ask_user
        if input_data.unclear_items:
            questions = self._generate_user_questions(input_data.unclear_items)
            if questions:
                return DP2RouterOutput(
                    decision="ask_user",
                    reason=f"Clarification needed for: {', '.join(input_data.unclear_items[:2])}",
                    user_questions=questions[:self.MAX_USER_QUESTIONS],
                )
        
        # 5. 품질 충분 → accept
        if input_data.quality_score >= self.QUALITY_THRESHOLD:
            return DP2RouterOutput(
                decision="accept_minor_issues",
                reason=f"Quality {input_data.quality_score:.0%} meets threshold",
            )
        
        # 기본: redesign
        return DP2RouterOutput(
            decision="redesign",
            reason=f"Quality {input_data.quality_score:.0%} below threshold, redesigning",
        )
    
    def _check_missing_required_controls(self, missing: list[str]) -> list[str]:
        """필수 대조군 누락 확인"""
        missing_lower = [m.lower() for m in missing]
        return [
            ctrl for ctrl in self.REQUIRED_CONTROLS
            if any(ctrl in m for m in missing_lower)
        ]
    
    def _get_searchable_gaps(
        self,
        gaps: list[str],
        previously_searched: list[str],
    ) -> list[str]:
        """검색 가능한 갭 (이전 검색 제외)"""
        return [g for g in gaps if g not in previously_searched]
    
    def _has_search_budget(self, input_data: DP2RouterInput) -> bool:
        """검색 예산 있는지 확인"""
        return (
            input_data.epmc_budget_remaining > 0 or
            input_data.web_budget_remaining > 0
        )
    
    def _generate_search_queries(self, gaps: list[str]) -> list[str]:
        """검색 쿼리 생성"""
        queries = []
        for gap in gaps[:3]:
            # 간단한 쿼리 생성 (실제로는 LLM 사용 가능)
            if "control" in gap.lower():
                queries.append(f"{gap} experimental protocol")
            elif "method" in gap.lower():
                queries.append(f"{gap} methodology")
            else:
                queries.append(f"{gap} evidence")
        return queries
    
    def _generate_user_questions(self, unclear_items: list[str]) -> list[str]:
        """사용자 질문 생성"""
        questions = []
        for item in unclear_items[:self.MAX_USER_QUESTIONS]:
            if "model" in item.lower():
                questions.append(f"Which specific model system do you prefer for {item}?")
            elif "assay" in item.lower():
                questions.append(f"What assay method would you like to use for {item}?")
            else:
                questions.append(f"Could you clarify your requirements for {item}?")
        return questions


# 싱글톤 인스턴스
dp2_critique_router = DP2CritiqueRouter()
