"""DP3 Synthesis Router - Plan A/B 분기 결정

최종 합성 전 Plan 구성 결정

규칙:
- plan_B_only: web 한도 초과 + 근거 부족 OR 명시적 제약
- plan_A_B: approval_required OR high cost/ethics
- single_plan: quality >= 0.8 + 충분한 근거 + 승인 불필요

Plan 정의:
- Plan A: 이상적 실험 설계 (모든 리소스 가용 가정)
- Plan B: 현실적 대안 (제약 조건 반영)
"""

import logging

from ..search.types import (
    DP3RouterInput,
    DP3RouterOutput,
    DP3Decision,
)

logger = logging.getLogger(__name__)

# 임계값
QUALITY_THRESHOLD = 0.80


class DP3SynthesisRouter:
    """DP3 Plan A/B 분기 라우터

    최종 합성 전 Plan 구성 결정:
    - single_plan: Plan A만 생성
    - plan_a_b: Plan A + B 동시 생성
    - plan_b_only: Plan B만 생성
    """

    def route(
        self,
        input_data: DP3RouterInput,
        run_id: str,
    ) -> DP3RouterOutput:
        """Plan A/B 분기 결정

        Args:
            input_data: 현재 상태
            run_id: 실행 ID

        Returns:
            DP3RouterOutput: Plan 구성 결정
        """
        quality = input_data.quality_score
        approval_required = input_data.approval_required
        web_limit_exceeded = input_data.web_limit_exceeded
        evidence_sufficient = input_data.evidence_sufficient
        high_cost = input_data.high_cost_experiment
        ethics_required = input_data.ethics_required
        explicit_constraints = input_data.explicit_constraints

        # 1. Plan B only: 강제 제약 조건
        if web_limit_exceeded and not evidence_sufficient:
            logger.info(
                "dp3_plan_b_only_web_limit run_id=%s",
                run_id,
            )
            return DP3RouterOutput(
                decision="plan_b_only",
                reason="Web 검색 한도 초과 + 근거 부족으로 Plan B만 생성",
                plan_config={
                    "constraint_type": "resource_limit",
                    "focus": "feasibility",
                },
            )

        if explicit_constraints:
            # 명시적 제약 있으면 Plan B only
            logger.info(
                "dp3_plan_b_only_constraints run_id=%s constraints=%s",
                run_id,
                explicit_constraints[:2],
            )
            return DP3RouterOutput(
                decision="plan_b_only",
                reason=f"명시적 제약 조건: {', '.join(explicit_constraints[:2])}",
                plan_config={
                    "constraint_type": "explicit",
                    "constraints": explicit_constraints,
                    "focus": "alternative_approach",
                },
            )

        # 2. Plan A + B: 승인 필요 또는 고비용/윤리 이슈
        if approval_required:
            logger.info(
                "dp3_plan_a_b_approval run_id=%s",
                run_id,
            )
            return DP3RouterOutput(
                decision="plan_a_b",
                reason="승인 필요 - Plan A(이상적) + Plan B(대안) 동시 제공",
                plan_config={
                    "approval_type": "general",
                    "plan_a_focus": "optimal_design",
                    "plan_b_focus": "practical_alternative",
                },
            )

        if high_cost:
            logger.info(
                "dp3_plan_a_b_high_cost run_id=%s",
                run_id,
            )
            return DP3RouterOutput(
                decision="plan_a_b",
                reason="고비용 실험 - Plan A(이상적) + Plan B(비용 최적화) 동시 제공",
                plan_config={
                    "approval_type": "budget",
                    "plan_a_focus": "optimal_design",
                    "plan_b_focus": "cost_effective",
                },
            )

        if ethics_required:
            logger.info(
                "dp3_plan_a_b_ethics run_id=%s",
                run_id,
            )
            return DP3RouterOutput(
                decision="plan_a_b",
                reason="윤리 승인 필요 - Plan A(이상적) + Plan B(윤리 최소화) 동시 제공",
                plan_config={
                    "approval_type": "ethics",
                    "plan_a_focus": "comprehensive",
                    "plan_b_focus": "minimal_animals",
                },
            )

        # 3. Single Plan: 충분한 품질 + 제약 없음
        if quality >= QUALITY_THRESHOLD and evidence_sufficient:
            logger.info(
                "dp3_single_plan run_id=%s quality=%.2f",
                run_id,
                quality,
            )
            return DP3RouterOutput(
                decision="single_plan",
                reason=f"품질 충분 (score={quality:.2f}) - 단일 최적 Plan 생성",
                plan_config={
                    "focus": "optimal",
                },
            )

        # 4. 기본: Plan A + B (안전한 선택)
        logger.info(
            "dp3_plan_a_b_default run_id=%s quality=%.2f",
            run_id,
            quality,
        )
        return DP3RouterOutput(
            decision="plan_a_b",
            reason="기본 선택 - Plan A(이상적) + Plan B(실현가능) 동시 제공",
            plan_config={
                "plan_a_focus": "optimal_design",
                "plan_b_focus": "practical_feasible",
            },
        )

    def get_plan_prompts(
        self,
        decision: DP3Decision,
        plan_config: dict,
    ) -> dict[str, str]:
        """Plan 생성용 프롬프트 반환

        Args:
            decision: DP3 결정
            plan_config: Plan 설정

        Returns:
            Plan 유형별 프롬프트
        """
        prompts = {}

        if decision == "single_plan":
            prompts["plan"] = self._get_optimal_plan_prompt(plan_config)

        elif decision == "plan_a_b":
            prompts["plan_a"] = self._get_plan_a_prompt(plan_config)
            prompts["plan_b"] = self._get_plan_b_prompt(plan_config)

        elif decision == "plan_b_only":
            prompts["plan_b"] = self._get_constrained_plan_prompt(plan_config)

        return prompts

    def _get_optimal_plan_prompt(self, config: dict) -> str:
        """최적 단일 Plan 프롬프트"""
        return """## 실험 계획

다음 조건을 만족하는 최적의 실험 계획을 작성하세요:
1. 가설 검증에 필요한 모든 실험 포함
2. 적절한 대조군 (vehicle, positive, negative)
3. 통계적 파워를 위한 충분한 샘플 크기
4. 측정 가능한 1차/2차 평가변수"""

    def _get_plan_a_prompt(self, config: dict) -> str:
        """Plan A (이상적) 프롬프트"""
        focus = config.get("plan_a_focus", "optimal_design")

        return f"""## Plan A: 이상적 실험 설계

리소스 제약 없이 **최적의 실험 설계**를 작성하세요.

목표: {focus}

포함 사항:
1. 완전한 대조군 세트 (vehicle, positive, rescue)
2. 충분한 샘플 크기와 반복
3. 모든 필요한 분석 방법
4. 시간 경과에 따른 종합적 측정"""

    def _get_plan_b_prompt(self, config: dict) -> str:
        """Plan B (현실적 대안) 프롬프트"""
        focus = config.get("plan_b_focus", "practical_alternative")
        approval_type = config.get("approval_type", "general")

        constraints = {
            "budget": "예산 제약을 고려하여 비용 효율적인 대안을 제시하세요.",
            "ethics": "동물 사용을 최소화하면서 핵심 가설을 검증할 수 있는 대안을 제시하세요.",
            "general": "현실적 제약을 고려한 실현 가능한 대안을 제시하세요.",
        }

        constraint_text = constraints.get(approval_type, constraints["general"])

        return f"""## Plan B: 현실적 대안

{constraint_text}

목표: {focus}

고려 사항:
1. 핵심 실험에 집중
2. 필수 대조군만 포함
3. 최소한의 샘플 크기
4. 1차 평가변수 우선"""

    def _get_constrained_plan_prompt(self, config: dict) -> str:
        """제약 조건 기반 Plan 프롬프트"""
        constraints = config.get("constraints", [])
        constraint_type = config.get("constraint_type", "resource_limit")
        focus = config.get("focus", "feasibility")

        if constraint_type == "explicit":
            constraint_text = f"다음 제약 조건을 반드시 준수하세요:\n" + "\n".join(
                f"- {c}" for c in constraints
            )
        else:
            constraint_text = "리소스 제한으로 인해 현실적인 대안만 제시하세요."

        return f"""## 실험 계획 (제약 조건 반영)

{constraint_text}

목표: {focus}

작성 지침:
1. 제약 조건 내에서 가능한 최선의 설계
2. 핵심 가설 검증에 집중
3. 단계적 접근 (pilot → full) 고려
4. 명확한 go/no-go 기준 포함"""
