"""DP2 Critique Router - Critique 후 전략 결정

Critique 결과를 분석하여 다음 행동 결정

규칙 (우선순위 순):
1. missing_controls (vehicle/positive/rescue) → redesign
2. evidence_gaps + budget 있음 → search_for_controls (같은 gap 2회 금지)
3. feasibility_conflicts → redesign (Plan B 방향)
4. 모델/assay 불명확 → ask_user (최대 3개)
5. quality >= 0.8 + 하드실패 없음 → accept_minor_issues
"""

import logging
from typing import Optional

from ..search.types import (
    DP2RouterInput,
    DP2RouterOutput,
    DP2Decision,
    SearchObjective,
    QueryPlan,
)

logger = logging.getLogger(__name__)

# 가드레일 상수
MAX_DP2_LOOPS = 2
MAX_USER_QUESTIONS = 3
QUALITY_THRESHOLD = 0.8

# 필수 대조군
REQUIRED_CONTROLS = {"vehicle", "positive", "rescue"}


class DP2CritiqueRouter:
    """DP2 Critique 전략 라우터

    Critique 결과를 분석하여 다음 행동 결정:
    - redesign: 설계 재작업
    - search_for_controls: 프로토콜/대조군 추가 검색
    - ask_user: 사용자 질문 (최대 3개)
    - accept_minor_issues: 경미한 이슈 수용
    """

    def route(
        self,
        input_data: DP2RouterInput,
        run_id: str,
    ) -> DP2RouterOutput:
        """Critique 후 전략 결정

        Args:
            input_data: Critique 결과
            run_id: 실행 ID

        Returns:
            DP2RouterOutput: 결정 및 상세 정보
        """
        quality = input_data.quality_score
        missing_controls = set(input_data.missing_controls)
        evidence_gaps = input_data.evidence_gaps
        feasibility_conflicts = input_data.feasibility_conflicts
        unclear_elements = input_data.unclear_elements
        loop_count = input_data.loop_count
        previous_gaps = set(input_data.previous_gaps_searched)
        budget_remaining = input_data.search_budget_remaining

        # 0. 루프 제한 체크
        if loop_count >= MAX_DP2_LOOPS:
            logger.warning(
                "dp2_loop_limit_reached run_id=%s loop_count=%d",
                run_id,
                loop_count,
            )
            return DP2RouterOutput(
                decision="accept_minor_issues",
                reason=f"DP2 루프 제한 도달 ({loop_count}/{MAX_DP2_LOOPS})",
            )

        # 1. 필수 대조군 누락 → redesign
        critical_missing = missing_controls & REQUIRED_CONTROLS
        if critical_missing:
            logger.info(
                "dp2_redesign_missing_controls run_id=%s missing=%s",
                run_id,
                critical_missing,
            )
            return DP2RouterOutput(
                decision="redesign",
                reason=f"필수 대조군 누락: {', '.join(critical_missing)}",
                target_gaps=list(critical_missing),
            )

        # 2. 근거 gap + 예산 있음 → search_for_controls
        if evidence_gaps and budget_remaining > 0:
            # 같은 gap 연속 검색 금지
            new_gaps = [g for g in evidence_gaps if g not in previous_gaps]

            if new_gaps:
                logger.info(
                    "dp2_search_for_controls run_id=%s gaps=%s",
                    run_id,
                    new_gaps[:2],
                )
                return DP2RouterOutput(
                    decision="search_for_controls",
                    reason=f"근거 보강 필요: {', '.join(new_gaps[:2])}",
                    target_gaps=new_gaps[:2],  # 최대 2개
                )
            else:
                logger.warning(
                    "dp2_same_gaps_blocked run_id=%s gaps=%s",
                    run_id,
                    evidence_gaps,
                )

        # 3. 실현가능성 충돌 → redesign (Plan B 방향)
        if feasibility_conflicts:
            logger.info(
                "dp2_redesign_feasibility run_id=%s conflicts=%s",
                run_id,
                feasibility_conflicts[:2],
            )
            return DP2RouterOutput(
                decision="redesign",
                reason=f"실현가능성 충돌: {', '.join(feasibility_conflicts[:2])}",
                target_gaps=feasibility_conflicts[:2],
            )

        # 4. 모델/assay 불명확 → ask_user
        if unclear_elements:
            questions = self._generate_user_questions(unclear_elements)
            if questions:
                logger.info(
                    "dp2_ask_user run_id=%s questions=%d",
                    run_id,
                    len(questions),
                )
                return DP2RouterOutput(
                    decision="ask_user",
                    reason=f"사용자 확인 필요: {len(questions)}개 항목",
                    user_questions=questions,
                )

        # 5. 품질 충분 + 하드실패 없음 → accept
        if quality >= QUALITY_THRESHOLD:
            logger.info(
                "dp2_accept run_id=%s quality=%.2f",
                run_id,
                quality,
            )
            return DP2RouterOutput(
                decision="accept_minor_issues",
                reason=f"품질 충분 (score={quality:.2f})",
            )

        # 6. 기본: 경미한 이슈 수용
        logger.info(
            "dp2_accept_default run_id=%s quality=%.2f",
            run_id,
            quality,
        )
        return DP2RouterOutput(
            decision="accept_minor_issues",
            reason=f"경미한 이슈 수용 (score={quality:.2f})",
        )

    def _generate_user_questions(
        self,
        unclear_elements: list[str],
    ) -> list[str]:
        """불명확 요소에서 사용자 질문 생성"""
        questions = []

        for element in unclear_elements[:MAX_USER_QUESTIONS]:
            element_lower = element.lower()

            # 키워드 기반 질문 생성
            if "model" in element_lower or "animal" in element_lower:
                questions.append(f"실험에 사용할 동물 모델을 지정해 주세요: {element}")
            elif "assay" in element_lower or "method" in element_lower:
                questions.append(f"사용할 분석 방법을 지정해 주세요: {element}")
            elif "dose" in element_lower or "concentration" in element_lower:
                questions.append(f"농도/용량 범위를 지정해 주세요: {element}")
            elif "time" in element_lower or "duration" in element_lower:
                questions.append(f"실험 기간을 지정해 주세요: {element}")
            else:
                questions.append(f"다음 항목을 명확히 해주세요: {element}")

        return questions[:MAX_USER_QUESTIONS]

    def generate_search_query_plan(
        self,
        target_gaps: list[str],
        hypothesis: str,
    ) -> QueryPlan:
        """gap 기반 검색 쿼리 계획 생성"""
        # gap 유형에 따른 objective 결정
        gap_text = " ".join(target_gaps).lower()

        if any(kw in gap_text for kw in ["control", "vehicle", "positive", "negative"]):
            objective = SearchObjective.PROTOCOL_CONTROLS
        elif any(kw in gap_text for kw in ["evidence", "reproducibility", "validation"]):
            objective = SearchObjective.EVIDENCE_STRENGTH
        else:
            objective = SearchObjective.MECHANISM

        # 쿼리 생성
        primary_query = f"{hypothesis[:50]} {' '.join(target_gaps[:2])}"

        return QueryPlan(
            objective=objective,
            primary_query=primary_query,
            fallback_queries=[
                f"{target_gaps[0]} experimental protocol" if target_gaps else "",
            ],
            filters={
                "year_from": 2018,
                "open_access_only": True,
                "max_results": 5,
            },
        )
