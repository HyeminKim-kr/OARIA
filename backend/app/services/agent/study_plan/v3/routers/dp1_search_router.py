"""DP1 Search Router

검색 승격 결정 라우터.

승격 규칙:
- RAG → EPMC: coverage < 0.70 OR evidence_density < 2
- EPMC → Web: coverage < 0.75 AND 핵심 질문 빈약 AND web_budget > 0
- Web budget 없으면: skip_web_limit → Plan B
"""

import logging

from ...shared.search.types import (
    SearchTier,
    SearchObjective,
    DP1RouterInput,
    DP1RouterOutput,
)

logger = logging.getLogger(__name__)


class DP1SearchRouter:
    """
    DP1: 검색 승격 결정 라우터
    
    현재 검색 결과를 분석하고 다음 티어로 승격할지 결정합니다.
    """
    
    # 승격 임계값
    COVERAGE_THRESHOLD_EPMC = 0.70  # RAG → EPMC
    COVERAGE_THRESHOLD_WEB = 0.75   # EPMC → Web
    MIN_EVIDENCE_DENSITY = 2        # 질문당 최소 근거 수
    
    def route(self, input_data: DP1RouterInput, run_id: str = "") -> DP1RouterOutput:
        """
        검색 승격 결정
        
        Args:
            input_data: DP1RouterInput
            run_id: 실행 ID (로깅용)
            
        Returns:
            DP1RouterOutput: 결정 결과
        """
        logger.info(
            f"[DP1] run_id={run_id} tier={input_data.current_tier.name} "
            f"coverage={input_data.coverage:.2f} density={input_data.evidence_density}"
        )
        
        # 현재 티어에 따른 분기
        if input_data.current_tier == SearchTier.RAG:
            return self._route_from_rag(input_data)
        elif input_data.current_tier == SearchTier.EPMC:
            return self._route_from_epmc(input_data)
        else:
            # WEB 이후는 더 승격 없음
            return DP1RouterOutput(
                decision="proceed",
                reason="Already at highest tier (Web)",
                next_tier=SearchTier.WEB,
            )
    
    def _route_from_rag(self, input_data: DP1RouterInput) -> DP1RouterOutput:
        """RAG 결과 후 라우팅"""
        
        # 승격 조건: 커버리지 낮음 OR 근거 밀도 낮음
        should_upgrade = (
            input_data.coverage < self.COVERAGE_THRESHOLD_EPMC or
            input_data.evidence_density < self.MIN_EVIDENCE_DENSITY
        )
        
        if should_upgrade and input_data.epmc_budget_remaining > 0:
            # 검색 목적 결정
            objective = self._determine_objective(input_data.gap_categories)
            
            return DP1RouterOutput(
                decision="upgrade_to_epmc",
                reason=self._get_upgrade_reason(input_data, "EPMC"),
                next_tier=SearchTier.EPMC,
                objective=objective,
                query_plan={"gap_categories": input_data.gap_categories},
            )
        
        return DP1RouterOutput(
            decision="proceed",
            reason=f"Coverage {input_data.coverage:.0%} sufficient for RAG tier",
            next_tier=SearchTier.RAG,
        )
    
    def _route_from_epmc(self, input_data: DP1RouterInput) -> DP1RouterOutput:
        """EPMC 결과 후 라우팅"""
        
        # 핵심 질문 커버 여부
        critical_gaps = [g for g in input_data.gap_categories if g in ["N", "S"]]
        has_critical_gaps = len(critical_gaps) > 0
        
        # 승격 조건
        should_upgrade = (
            input_data.coverage < self.COVERAGE_THRESHOLD_WEB and
            has_critical_gaps
        )
        
        if should_upgrade:
            # Web 예산 확인
            if input_data.web_budget_remaining > 0:
                objective = self._determine_objective(critical_gaps)
                
                return DP1RouterOutput(
                    decision="upgrade_to_web",
                    reason=f"Critical gaps ({', '.join(critical_gaps)}) need web search",
                    next_tier=SearchTier.WEB,
                    objective=objective,
                    query_plan={"critical_gaps": critical_gaps},
                )
            else:
                # Web 예산 없음 → Plan B 방향
                return DP1RouterOutput(
                    decision="skip_web_limit",
                    reason="Web budget exhausted, proceeding with limited evidence",
                    next_tier=SearchTier.EPMC,
                    query_plan={"fallback": True, "gaps": critical_gaps},
                )
        
        return DP1RouterOutput(
            decision="proceed",
            reason=f"Coverage {input_data.coverage:.0%} sufficient after EPMC",
            next_tier=SearchTier.EPMC,
        )
    
    def _determine_objective(self, gap_categories: list[str]) -> SearchObjective:
        """갭 카테고리에서 검색 목적 결정"""
        # N (Necessity), S (Sufficiency) → mechanism
        # P (Protocol) → protocol_controls
        # E (Epistasis) → evidence_strength
        
        if "N" in gap_categories or "S" in gap_categories:
            return SearchObjective.MECHANISM
        elif "P" in gap_categories:
            return SearchObjective.PROTOCOL_CONTROLS
        else:
            return SearchObjective.EVIDENCE_STRENGTH
    
    def _get_upgrade_reason(self, input_data: DP1RouterInput, target: str) -> str:
        """승격 이유 생성"""
        reasons = []
        
        if input_data.coverage < self.COVERAGE_THRESHOLD_EPMC:
            reasons.append(f"coverage {input_data.coverage:.0%} below threshold")
        
        if input_data.evidence_density < self.MIN_EVIDENCE_DENSITY:
            reasons.append(f"evidence density {input_data.evidence_density} too low")
        
        if input_data.gap_categories:
            reasons.append(f"gaps in {', '.join(input_data.gap_categories[:3])}")
        
        return f"Upgrading to {target}: " + "; ".join(reasons)


# 싱글톤 인스턴스
dp1_search_router = DP1SearchRouter()
