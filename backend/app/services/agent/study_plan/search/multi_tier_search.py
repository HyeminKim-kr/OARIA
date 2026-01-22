"""Multi-Tier Search Service - 3-tier 검색 통합

3-tier 검색 스택 통합:
- Tier 1: RAG (Weaviate 벡터 검색)
- Tier 2: Europe PMC API
- Tier 3: Tavily Web Search

DP1 Router와 연동하여 자동 승격
"""

import logging
import time
import uuid
import hashlib
from typing import Optional

from ..rag.search import study_search_service
from ..rag.types import SearchResult as RagSearchResult

from .types import (
    SearchTier,
    SearchObjective,
    ClaimType,
    EvidenceSnippetV3,
    QueryPlan,
    TierSearchResult,
    MultiTierSearchResult,
    DP1RouterOutput,
)
from .europe_pmc_service import europe_pmc_service
from .tavily_service import tavily_service
from .budget_manager import budget_manager
from .cache_manager import cache_manager

logger = logging.getLogger(__name__)


class MultiTierSearchService:
    """3-tier 검색 서비스

    DP1 Router의 결정에 따라 tier를 승격하며 검색
    """

    async def search_tier1_rag(
        self,
        queries: list[str],
        hypothesis: str,
        run_id: str,
        year_from: int | None = None,
        sections: list[str] | None = None,
    ) -> TierSearchResult:
        """Tier 1: RAG 검색 (Weaviate)

        Args:
            queries: 검색 쿼리 목록
            hypothesis: 원본 가설 (캐시 키용)
            run_id: 실행 ID
            year_from: 연도 필터
            sections: 섹션 필터

        Returns:
            TierSearchResult
        """
        start_time = time.perf_counter()

        # 캐시 확인
        query_key = {"queries": queries, "year_from": year_from, "sections": sections}
        cached = await cache_manager.get(SearchTier.RAG, query_key, hypothesis)
        if cached is not None:
            return TierSearchResult(
                tier=SearchTier.RAG,
                snippets=cached,
                total_found=len(cached),
                coverage_score=self._calculate_coverage(cached),
                queries_used=queries,
                latency_ms=int((time.perf_counter() - start_time) * 1000),
                cached=True,
            )

        # RAG 검색 실행
        result: RagSearchResult = await study_search_service.search_studies(
            queries=queries,
            year_from=year_from,
            sections=sections,
        )

        # EvidenceSnippetV3로 변환
        snippets = self._convert_rag_to_v3(result)

        # 캐시 저장
        await cache_manager.set(SearchTier.RAG, query_key, hypothesis, snippets)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "tier1_rag_search run_id=%s papers=%d snippets=%d coverage=%.2f latency=%dms",
            run_id,
            result.total_papers,
            len(snippets),
            result.coverage_score,
            latency_ms,
        )

        return TierSearchResult(
            tier=SearchTier.RAG,
            snippets=snippets,
            total_found=result.total_snippets,
            coverage_score=result.coverage_score,
            queries_used=result.queries_used,
            latency_ms=latency_ms,
            cached=False,
        )

    async def search_tier2_epmc(
        self,
        query_plan: QueryPlan,
        hypothesis: str,
        run_id: str,
    ) -> TierSearchResult:
        """Tier 2: Europe PMC 검색

        Args:
            query_plan: 검색 계획 (objective, queries, filters)
            hypothesis: 원본 가설
            run_id: 실행 ID

        Returns:
            TierSearchResult
        """
        start_time = time.perf_counter()

        # 예산 확인
        can_use = await budget_manager.can_use_tier(run_id, SearchTier.EPMC)
        if not can_use:
            logger.warning("tier2_epmc_budget_exceeded run_id=%s", run_id)
            return TierSearchResult(
                tier=SearchTier.EPMC,
                snippets=[],
                total_found=0,
                coverage_score=0.0,
                queries_used=[query_plan.primary_query],
                latency_ms=0,
                cached=False,
            )

        # 캐시 확인
        cached = await cache_manager.get(
            SearchTier.EPMC, query_plan.to_dict(), hypothesis
        )
        if cached is not None:
            return TierSearchResult(
                tier=SearchTier.EPMC,
                snippets=cached,
                total_found=len(cached),
                coverage_score=self._calculate_coverage(cached),
                queries_used=[query_plan.primary_query],
                latency_ms=int((time.perf_counter() - start_time) * 1000),
                cached=True,
            )

        # 예산 증가
        await budget_manager.increment_run(run_id, SearchTier.EPMC)

        # Claim type 결정
        claim_type = self._objective_to_claim_type(query_plan.objective)

        # EPMC 검색 실행
        snippets = await europe_pmc_service.search_and_extract(
            query=query_plan.primary_query,
            claim_type=claim_type,
            open_access_only=query_plan.filters.get("open_access_only", True),
            year_from=query_plan.filters.get("year_from"),
            max_results=query_plan.filters.get("max_results", 10),
            extract_fulltext=query_plan.filters.get("extract_fulltext", False),
        )

        # Fallback 쿼리 실행 (결과가 적으면)
        if len(snippets) < 3 and query_plan.fallback_queries:
            for fallback_query in query_plan.fallback_queries[:2]:
                additional = await europe_pmc_service.search_and_extract(
                    query=fallback_query,
                    claim_type=claim_type,
                    open_access_only=query_plan.filters.get("open_access_only", True),
                    year_from=query_plan.filters.get("year_from"),
                    max_results=5,
                )
                snippets.extend(additional)

        # 캐시 저장
        await cache_manager.set(SearchTier.EPMC, query_plan.to_dict(), hypothesis, snippets)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "tier2_epmc_search run_id=%s snippets=%d latency=%dms",
            run_id,
            len(snippets),
            latency_ms,
        )

        return TierSearchResult(
            tier=SearchTier.EPMC,
            snippets=snippets,
            total_found=len(snippets),
            coverage_score=self._calculate_coverage(snippets),
            queries_used=[query_plan.primary_query] + query_plan.fallback_queries[:2],
            latency_ms=latency_ms,
            cached=False,
        )

    async def search_tier3_web(
        self,
        query: str,
        hypothesis: str,
        run_id: str,
        claim_type: ClaimType = ClaimType.MECHANISM,
    ) -> TierSearchResult:
        """Tier 3: Tavily Web 검색

        Args:
            query: 검색 쿼리
            hypothesis: 원본 가설
            run_id: 실행 ID
            claim_type: Evidence 유형

        Returns:
            TierSearchResult
        """
        start_time = time.perf_counter()

        # 예산 확인
        can_use = await budget_manager.can_use_tier(run_id, SearchTier.WEB)
        if not can_use:
            logger.warning("tier3_web_budget_exceeded run_id=%s", run_id)
            return TierSearchResult(
                tier=SearchTier.WEB,
                snippets=[],
                total_found=0,
                coverage_score=0.0,
                queries_used=[query],
                latency_ms=0,
                cached=False,
            )

        # 캐시 확인
        cached = await cache_manager.get(SearchTier.WEB, query, hypothesis)
        if cached is not None:
            return TierSearchResult(
                tier=SearchTier.WEB,
                snippets=cached,
                total_found=len(cached),
                coverage_score=self._calculate_coverage(cached),
                queries_used=[query],
                latency_ms=int((time.perf_counter() - start_time) * 1000),
                cached=True,
            )

        # 예산 증가
        await budget_manager.increment_run(run_id, SearchTier.WEB)

        # Tavily 검색 실행
        snippets = await tavily_service.search_for_evidence(
            query=query,
            claim_type=claim_type,
            search_depth="basic",
            max_results=5,
            academic_focus=True,
        )

        # 캐시 저장
        await cache_manager.set(SearchTier.WEB, query, hypothesis, snippets)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            "tier3_web_search run_id=%s snippets=%d latency=%dms",
            run_id,
            len(snippets),
            latency_ms,
        )

        return TierSearchResult(
            tier=SearchTier.WEB,
            snippets=snippets,
            total_found=len(snippets),
            coverage_score=self._calculate_coverage(snippets),
            queries_used=[query],
            latency_ms=latency_ms,
            cached=False,
        )

    async def search_with_escalation(
        self,
        queries: list[str],
        hypothesis: str,
        run_id: str,
        dp1_decisions: list[DP1RouterOutput],
        year_from: int | None = None,
    ) -> MultiTierSearchResult:
        """DP1 결정에 따른 단계별 검색

        DP1 Router가 결정한 승격 경로를 따라 검색을 수행합니다.

        Args:
            queries: RAG 검색 쿼리
            hypothesis: 원본 가설
            run_id: 실행 ID
            dp1_decisions: DP1 Router 결정 이력
            year_from: 연도 필터

        Returns:
            MultiTierSearchResult
        """
        tier_results: dict[SearchTier, TierSearchResult] = {}
        all_snippets: list[EvidenceSnippetV3] = []

        # 1. RAG 검색 (항상 실행)
        rag_result = await self.search_tier1_rag(
            queries=queries,
            hypothesis=hypothesis,
            run_id=run_id,
            year_from=year_from,
        )
        tier_results[SearchTier.RAG] = rag_result
        all_snippets.extend(rag_result.snippets)

        highest_tier = SearchTier.RAG

        # 2. DP1 결정에 따른 승격
        for decision in dp1_decisions:
            if decision.decision == "upgrade_to_epmc" and decision.query_plan:
                epmc_result = await self.search_tier2_epmc(
                    query_plan=decision.query_plan,
                    hypothesis=hypothesis,
                    run_id=run_id,
                )
                tier_results[SearchTier.EPMC] = epmc_result
                all_snippets.extend(epmc_result.snippets)
                highest_tier = SearchTier.EPMC

            elif decision.decision == "upgrade_to_web" and decision.query_plan:
                web_result = await self.search_tier3_web(
                    query=decision.query_plan.primary_query,
                    hypothesis=hypothesis,
                    run_id=run_id,
                    claim_type=self._objective_to_claim_type(decision.objective),
                )
                tier_results[SearchTier.WEB] = web_result
                all_snippets.extend(web_result.snippets)
                highest_tier = SearchTier.WEB

        # 중복 제거 및 정렬
        unique_snippets = self._deduplicate_snippets(all_snippets)

        # 전체 coverage 계산
        total_coverage = self._calculate_total_coverage(tier_results)

        return MultiTierSearchResult(
            tier_results=tier_results,
            final_snippets=unique_snippets,
            highest_tier_used=highest_tier,
            total_coverage_score=total_coverage,
            dp1_decisions=dp1_decisions,
        )

    def _convert_rag_to_v3(self, result: RagSearchResult) -> list[EvidenceSnippetV3]:
        """RAG SearchResult를 EvidenceSnippetV3로 변환"""
        snippets = []

        for paper in result.papers:
            for snippet in paper.snippets:
                snippets.append(
                    EvidenceSnippetV3(
                        snippet_id=f"rag_{snippet.snippet_id}",
                        text=snippet.text,
                        source_tier=SearchTier.RAG,
                        source_tool="weaviate",
                        claim_type=ClaimType.MECHANISM,  # 기본값, 나중에 분류
                        paper_id=paper.paper_id,
                        title=paper.title,
                        journal=paper.journal,
                        year=paper.year,
                        section=snippet.section,
                        relevance_score=snippet.relevance_score,
                        offset_start=snippet.offset_start,
                        offset_end=snippet.offset_end,
                        text_version=snippet.text_version,
                    )
                )

        return snippets

    def _objective_to_claim_type(
        self, objective: SearchObjective | None
    ) -> ClaimType:
        """SearchObjective를 ClaimType으로 변환"""
        if objective == SearchObjective.MECHANISM:
            return ClaimType.MECHANISM
        elif objective == SearchObjective.PROTOCOL_CONTROLS:
            return ClaimType.PROTOCOL
        elif objective == SearchObjective.EVIDENCE_STRENGTH:
            return ClaimType.RESULT
        return ClaimType.MECHANISM

    def _calculate_coverage(self, snippets: list[EvidenceSnippetV3]) -> float:
        """스니펫 기반 coverage 계산"""
        if not snippets:
            return 0.0

        # 스니펫 수 기반 (0-0.5)
        count_score = min(len(snippets) / 20, 1.0) * 0.5

        # 고품질 스니펫 비율 (0-0.3)
        high_quality = sum(1 for s in snippets if s.relevance_score >= 0.7)
        quality_ratio = high_quality / len(snippets) if snippets else 0
        quality_score = quality_ratio * 0.3

        # 소스 다양성 (0-0.2)
        unique_sources = len(set(s.paper_id or s.url for s in snippets))
        diversity_score = min(unique_sources / 10, 1.0) * 0.2

        return count_score + quality_score + diversity_score

    def _calculate_total_coverage(
        self, tier_results: dict[SearchTier, TierSearchResult]
    ) -> float:
        """전체 tier coverage 계산 (가중 평균)"""
        if not tier_results:
            return 0.0

        # tier별 가중치
        weights = {
            SearchTier.RAG: 0.5,
            SearchTier.EPMC: 0.3,
            SearchTier.WEB: 0.2,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for tier, result in tier_results.items():
            weight = weights.get(tier, 0.2)
            weighted_sum += result.coverage_score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _deduplicate_snippets(
        self, snippets: list[EvidenceSnippetV3]
    ) -> list[EvidenceSnippetV3]:
        """스니펫 중복 제거 (텍스트 해시 기반)"""
        seen_hashes: set[str] = set()
        unique: list[EvidenceSnippetV3] = []

        for snippet in snippets:
            # 텍스트 해시로 중복 체크
            text_hash = hashlib.md5(snippet.text[:500].encode()).hexdigest()

            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                unique.append(snippet)

        # relevance_score로 정렬
        unique.sort(key=lambda s: s.relevance_score, reverse=True)

        return unique


# 싱글톤 인스턴스
multi_tier_search = MultiTierSearchService()
