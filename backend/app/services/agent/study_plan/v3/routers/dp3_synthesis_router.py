"""DP3 Synthesis Router

Plan A/B 분기 결정 라우터.

규칙:
- plan_B_only: web 한도 초과 + 근거 부족 OR 명시적 제약
- plan_A_B: approval_required OR high cost/ethics
- single_plan: quality >= 0.8 + 충분한 근거 + 승인 불필요
"""

import logging
from dataclasses import dataclass, field

from ...shared.search.types import DP3RouterInput, DP3RouterOutput

logger = logging.getLogger(__name__)


class DP3SynthesisRouter:
    """
    DP3: Plan A/B 분기 결정 라우터
    
    최종 계획 합성 전에 Plan 유형을 결정합니다.
    """
    
    def route(self, input_data: DP3RouterInput, run_id: str = "") -> DP3RouterOutput:
        """
        Plan 유형 결정
        
        Args:
            input_data: DP3RouterInput
            run_id: 실행 ID (로깅용)
            
        Returns:
            DP3RouterOutput: 결정 결과
        """
        logger.info(f"[DP3] run_id={run_id} quality={input_data.quality_score:.2f} "
                   f"approval={input_data.approval_required} "
                   f"web_exceeded={input_data.web_limit_exceeded}")
        
        # 1. Plan B only 조건
        # - web 한도 초과 + 근거 부족
        # - 명시적 제약 있음
        if self._should_plan_b_only(input_data):
            decision = "plan_b_only"
            reason = self._get_plan_b_reason(input_data)
            plan_config = {
                "focus": "feasibility",
                "include_alternatives": True,
                "emphasize_go_nogo": True,
            }
            
        # 2. Plan A/B 조건
        # - 승인 필요 (고비용/윤리)
        # - high cost experiment
        # - ethics required
        elif self._should_plan_ab(input_data):
            decision = "plan_a_b"
            reason = self._get_plan_ab_reason(input_data)
            plan_config = {
                "plan_a_focus": "optimal_design",
                "plan_b_focus": "minimal_viable",
                "comparison": True,
            }
            
        # 3. Single Plan (기본)
        else:
            decision = "single_plan"
            reason = "Quality sufficient, no special constraints"
            plan_config = {
                "comprehensive": True,
                "include_alternatives": False,
            }
        
        logger.info(f"[DP3] Decision: {decision} - {reason}")
        
        return DP3RouterOutput(
            decision=decision,
            reason=reason,
            plan_config=plan_config,
        )
    
    def _should_plan_b_only(self, input_data: DP3RouterInput) -> bool:
        """Plan B only 조건 체크"""
        # web 한도 초과 + 근거 부족
        if input_data.web_limit_exceeded and not input_data.evidence_sufficient:
            return True
        
        # 명시적 제약 중 "예산 제한", "시간 제약" 등이 있는 경우
        constraint_keywords = ["budget", "예산", "time", "시간", "minimal", "최소"]
        for constraint in input_data.explicit_constraints:
            if any(kw in constraint.lower() for kw in constraint_keywords):
                return True
        
        return False
    
    def _should_plan_ab(self, input_data: DP3RouterInput) -> bool:
        """Plan A/B 조건 체크"""
        # 승인 필요
        if input_data.approval_required:
            return True
        
        # 고비용 실험
        if input_data.high_cost_experiment:
            return True
        
        # 윤리 심의 필요
        if input_data.ethics_required:
            return True
        
        # 품질이 중간 범위 (0.6~0.8)이고 근거가 충분한 경우
        # → 사용자에게 선택권 제공
        if 0.6 <= input_data.quality_score < 0.8 and input_data.evidence_sufficient:
            return True
        
        return False
    
    def _get_plan_b_reason(self, input_data: DP3RouterInput) -> str:
        """Plan B only 이유 생성"""
        reasons = []
        
        if input_data.web_limit_exceeded and not input_data.evidence_sufficient:
            reasons.append("Web search limit exceeded with insufficient evidence")
        
        if input_data.explicit_constraints:
            reasons.append(f"Explicit constraints: {', '.join(input_data.explicit_constraints[:2])}")
        
        return "; ".join(reasons) if reasons else "Resource constraints detected"
    
    def _get_plan_ab_reason(self, input_data: DP3RouterInput) -> str:
        """Plan A/B 이유 생성"""
        reasons = []
        
        if input_data.approval_required:
            reasons.append("Approval required")
        
        if input_data.high_cost_experiment:
            reasons.append("High-cost experiment")
        
        if input_data.ethics_required:
            reasons.append("Ethics review required")
        
        if 0.6 <= input_data.quality_score < 0.8:
            reasons.append(f"Quality score {input_data.quality_score:.0%} in decision range")
        
        return "; ".join(reasons) if reasons else "Multiple options available"
    
    def get_plan_prompts(self, decision: str, plan_config: dict) -> dict:
        """
        결정에 따른 Plan 생성 프롬프트 반환
        
        Args:
            decision: single_plan | plan_a_b | plan_b_only
            plan_config: 설정 딕셔너리
            
        Returns:
            프롬프트 딕셔너리 (plan, plan_a, plan_b 키 포함)
        """
        if decision == "single_plan":
            return {
                "plan": """
Based on the provided context, create a comprehensive research plan.
Balance between optimal design and practical feasibility.
Include all necessary controls and validation steps.
""",
            }
        
        elif decision == "plan_a_b":
            return {
                "plan_a": """
Create an IDEAL research plan (Plan A).
Assume all resources are available.
Focus on optimal experimental design without constraints.
Include gold-standard controls and comprehensive measurements.
""",
                "plan_b": """
Create a PRACTICAL alternative plan (Plan B).
Consider resource constraints and timeline limitations.
Focus on essential experiments with clear go/no-go criteria.
Include cost-effective alternatives and minimum viable experiments.
""",
            }
        
        elif decision == "plan_b_only":
            return {
                "plan_b": """
Create a RESOURCE-CONSTRAINED research plan.
Given the limitations, focus on:
1. Essential experiments only
2. Clear go/no-go decision points
3. Cost-effective methods
4. Minimum viable protocol
5. Alternative low-cost approaches
""",
            }
        
        return {"plan": ""}
