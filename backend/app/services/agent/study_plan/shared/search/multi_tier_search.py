"""Multi-Tier Search Service

3-tier 검색 통합 서비스.
- Tier 1: RAG (Weaviate)
- Tier 2: Europe PMC
- Tier 3: Tavily Web
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .types import SearchTier, SearchObjective, EvidenceSnippetV3
from .budget_manager import budget_manager
from .cache_manager import cache_manager
from .europe_pmc_service import europe_pmc_service, EPMCPaper
from .tavily_service import tavily_service, TavilyResult

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """통합 검색 결과"""
    snippets: list[EvidenceSnippetV3]
    tier: SearchTier
    coverage: float  # 0.0 ~ 1.0
    gaps: list[str]  # 커버리지 부족 영역
    query_used: str
    total_papers: int = 0


class MultiTierSearchService:
    """
    3-tier 검색 통합 서비스
    
    1. RAG 검색 (내부 Weaviate)
    2. Europe PMC 검색
    3. Tavily Web 검색
    """
    
    async def search_tier1_rag(
        self,
        queries: list[str],
        run_id: str,
        hypothesis_hash: str,
    ) -> SearchResult:
        """
        Tier 1: RAG 검색
        
        Args:
            queries: 검색 쿼리 목록
            run_id: 실행 ID
            hypothesis_hash: 가설 해시 (캐시용)
            
        Returns:
            SearchResult
        """
        # 캐시 확인
        query_plan = {"tier": "rag", "queries": queries}
        cached = await cache_manager.get("rag", query_plan, hypothesis_hash)
        if cached:
            return SearchResult(**cached)
        
        # RAG 검색 수행 (기존 RAG 서비스 사용)
        snippets = []
        
        try:
            # 기존 RAG 서비스 import
            from ..rag.search import rag_search_service
            
            for query in queries:
                results = await rag_search_service.search(query, limit=10)
                for r in results:
                    snippet = EvidenceSnippetV3(
                        paper_id=r.paper_id,
                        title=r.title,
                        journal=r.journal or "",
                        year=r.year or 0,
                        snippet=r.snippet,
                        claim_type="mechanism",
                        source_tier=SearchTier.RAG,
                        source_tool="weaviate",
                        relevance_score=1.0 - r.distance,
                        metadata={"chunk_id": r.chunk_id, "section": r.section},
                    )
                    snippets.append(snippet)
                    
        except Exception as e:
            logger.error(f"[MultiTier] RAG search failed: {e}")
        
        # 커버리지 계산 (간단한 휴리스틱)
        unique_papers = len(set(s.paper_id for s in snippets))
        coverage = min(1.0, unique_papers / max(len(queries) * 2, 1))
        gaps = self._identify_gaps(queries, snippets)
        
        result = SearchResult(
            snippets=snippets,
            tier=SearchTier.RAG,
            coverage=coverage,
            gaps=gaps,
            query_used=" | ".join(queries),
            total_papers=unique_papers,
        )
        
        # 캐시 저장
        await cache_manager.set("rag", query_plan, result.__dict__, hypothesis_hash)
        
        logger.info(f"[MultiTier] RAG: {len(snippets)} snippets, coverage={coverage:.2f}")
        return result
    
    async def search_tier2_epmc(
        self,
        query: str,
        objective: SearchObjective,
        run_id: str,
        hypothesis_hash: str,
    ) -> SearchResult:
        """
        Tier 2: Europe PMC 검색
        
        Args:
            query: 검색 쿼리
            objective: 검색 목적
            run_id: 실행 ID
            hypothesis_hash: 가설 해시
            
        Returns:
            SearchResult
        """
        # 예산 확인
        if not await budget_manager.can_use_epmc(run_id):
            logger.warning(f"[MultiTier] EPMC budget exceeded for {run_id}")
            return SearchResult(
                snippets=[],
                tier=SearchTier.EPMC,
                coverage=0.0,
                gaps=["budget_exceeded"],
                query_used=query,
            )
        
        # 캐시 확인
        query_plan = {"tier": "epmc", "query": query, "objective": objective.value}
        cached = await cache_manager.get("epmc", query_plan, hypothesis_hash)
        if cached:
            return SearchResult(**cached)
        
        # EPMC 검색
        budget_manager.increment_epmc(run_id)
        
        search_result = await europe_pmc_service.search(
            query=query,
            open_access_only=True,
            year_from=2018,
            max_results=20,
        )
        
        snippets = []
        for paper in search_result.papers:
            snippet = EvidenceSnippetV3(
                paper_id=paper.pmcid or paper.pmid or "",
                title=paper.title,
                journal=paper.journal,
                year=paper.year,
                snippet=paper.abstract[:500] if paper.abstract else "",
                claim_type=objective.value,
                source_tier=SearchTier.EPMC,
                source_tool="europe_pmc",
                relevance_score=0.8,
                metadata={"pmid": paper.pmid, "citations": paper.citations},
            )
            snippets.append(snippet)
        
        coverage = min(1.0, len(snippets) / 10)
        
        result = SearchResult(
            snippets=snippets,
            tier=SearchTier.EPMC,
            coverage=coverage,
            gaps=[],
            query_used=query,
            total_papers=search_result.total_count,
        )
        
        # 캐시 저장
        await cache_manager.set("epmc", query_plan, result.__dict__, hypothesis_hash)
        
        logger.info(f"[MultiTier] EPMC: {len(snippets)} papers, coverage={coverage:.2f}")
        return result
    
    async def search_tier3_web(
        self,
        query: str,
        objective: SearchObjective,
        run_id: str,
        hypothesis_hash: str,
    ) -> SearchResult:
        """
        Tier 3: Tavily Web 검색
        
        Args:
            query: 검색 쿼리
            objective: 검색 목적
            run_id: 실행 ID
            hypothesis_hash: 가설 해시
            
        Returns:
            SearchResult
        """
        # 예산 확인
        if not await budget_manager.can_use_web(run_id):
            logger.warning(f"[MultiTier] Web budget exceeded for {run_id}")
            return SearchResult(
                snippets=[],
                tier=SearchTier.WEB,
                coverage=0.0,
                gaps=["web_budget_exceeded"],
                query_used=query,
            )
        
        # 캐시 확인
        query_plan = {"tier": "web", "query": query, "objective": objective.value}
        cached = await cache_manager.get("web", query_plan, hypothesis_hash)
        if cached:
            return SearchResult(**cached)
        
        # Tavily 검색
        await budget_manager.increment_web(run_id)
        
        search_result = await tavily_service.search(
            query=query,
            search_depth="advanced",
            max_results=5,
        )
        
        snippets = []
        for item in search_result.results:
            snippet = EvidenceSnippetV3(
                paper_id=item.url,
                title=item.title,
                journal="web",
                year=0,
                snippet=item.content[:500] if item.content else "",
                claim_type=objective.value,
                source_tier=SearchTier.WEB,
                source_tool="tavily",
                relevance_score=item.score,
                metadata={"url": item.url, "published_date": item.published_date},
            )
            snippets.append(snippet)
        
        coverage = min(1.0, len(snippets) / 3)
        
        result = SearchResult(
            snippets=snippets,
            tier=SearchTier.WEB,
            coverage=coverage,
            gaps=[],
            query_used=query,
            total_papers=len(search_result.results),
        )
        
        # 캐시 저장
        await cache_manager.set("web", query_plan, result.__dict__, hypothesis_hash)
        
        logger.info(f"[MultiTier] Web: {len(snippets)} results, coverage={coverage:.2f}")
        return result
    
    def _identify_gaps(
        self,
        queries: list[str],
        snippets: list[EvidenceSnippetV3],
    ) -> list[str]:
        """커버리지 부족 영역 식별"""
        gaps = []
        
        # 쿼리별 결과 확인
        snippet_texts = " ".join(s.snippet.lower() for s in snippets)
        
        for query in queries:
            keywords = query.lower().split()[:3]  # 주요 키워드
            if not any(kw in snippet_texts for kw in keywords):
                gaps.append(query[:50])
        
        return gaps[:5]  # 최대 5개
    
    @staticmethod
    def hash_hypothesis(hypothesis: str) -> str:
        """가설 해시 생성"""
        return hashlib.md5(hypothesis.lower().strip().encode()).hexdigest()[:12]


# 싱글톤 인스턴스
multi_tier_search = MultiTierSearchService()
