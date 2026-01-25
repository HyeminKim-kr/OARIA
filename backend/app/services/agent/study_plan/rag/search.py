"""Study Plan Agent 전용 통합 검색 서비스

3-tier 검색 통합:
- Tier 1: Weaviate (내부 벡터 DB)
- Tier 2: Europe PMC (외부 논문 API)
- Tier 3: Tavily (웹 검색)
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from .types import SearchResult, PaperResult, SnippetResult

logger = logging.getLogger(__name__)


class StudySearchService:
    """Study Plan Agent 전용 통합 검색 서비스

    3-tier 검색을 순차적으로 수행:
    1. Weaviate (내부 RAG) - 가장 빠름
    2. Europe PMC - 외부 논문 검색
    3. Tavily - 웹 검색 (프로토콜, 시약 정보 등)
    """

    def __init__(
        self,
        top_k_per_query: int = 5,
        max_queries: int = 8,
        use_reranker: bool = True,
        min_relevance_score: float = 0.3,
        enable_weaviate: bool = True,
        enable_epmc: bool = True,
        enable_tavily: bool = True,
    ):
        self.top_k_per_query = top_k_per_query
        self.max_queries = max_queries
        self.use_reranker = use_reranker
        self.min_relevance_score = min_relevance_score
        self.enable_weaviate = enable_weaviate
        self.enable_epmc = enable_epmc
        self.enable_tavily = enable_tavily

    async def search_studies(
        self,
        queries: list[str],
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
    ) -> SearchResult:
        """다중 쿼리로 논문 검색 (3-tier 통합)

        Args:
            queries: 검색 쿼리 목록
            year_from: 연도 필터 (이상)
            year_to: 연도 필터 (이하)
            sections: 섹션 필터 (abstract, methods, results, discussion)

        Returns:
            SearchResult: 검색 결과 집계
        """
        start_time = time.perf_counter()

        # 쿼리 수 제한
        limited_queries = queries[: self.max_queries]
        logger.info(f"[StudySearch] Searching with {len(limited_queries)} queries")

        paper_map: dict[str, PaperResult] = {}
        total_snippets = 0
        tiers_used: list[str] = []

        # Tier 1: Weaviate (내부 RAG)
        if self.enable_weaviate:
            try:
                weaviate_results = await self._search_weaviate(
                    queries=limited_queries,
                    year_from=year_from,
                    year_to=year_to,
                    sections=sections,
                )
                self._merge_results(paper_map, weaviate_results)
                if weaviate_results:
                    tiers_used.append("weaviate")
                    total_snippets += sum(len(p.snippets) for p in weaviate_results)
                logger.info(f"[StudySearch] Weaviate: {len(weaviate_results)} papers")
            except Exception as e:
                logger.warning(f"[StudySearch] Weaviate search failed: {e}")

        # Tier 2: Europe PMC
        if self.enable_epmc:
            try:
                epmc_results = await self._search_epmc(
                    queries=limited_queries,
                    year_from=year_from,
                    year_to=year_to,
                )
                self._merge_results(paper_map, epmc_results)
                if epmc_results:
                    tiers_used.append("epmc")
                    total_snippets += sum(len(p.snippets) for p in epmc_results)
                logger.info(f"[StudySearch] Europe PMC: {len(epmc_results)} papers")
            except Exception as e:
                logger.warning(f"[StudySearch] Europe PMC search failed: {e}")

        # Tier 3: Tavily (웹 검색)
        if self.enable_tavily:
            try:
                tavily_results = await self._search_tavily(queries=limited_queries)
                self._merge_results(paper_map, tavily_results)
                if tavily_results:
                    tiers_used.append("tavily")
                    total_snippets += sum(len(p.snippets) for p in tavily_results)
                logger.info(f"[StudySearch] Tavily: {len(tavily_results)} results")
            except Exception as e:
                logger.warning(f"[StudySearch] Tavily search failed: {e}")

        # 관련성 점수로 정렬
        papers = sorted(
            paper_map.values(),
            key=lambda p: p.max_relevance_score,
            reverse=True,
        )

        # 커버리지 점수 계산
        coverage_score = self._calculate_coverage(papers, len(limited_queries))

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"[StudySearch] Completed: {len(papers)} papers, "
            f"{total_snippets} snippets, coverage={coverage_score:.2f}, "
            f"tiers={tiers_used}, latency={elapsed_ms}ms"
        )

        return SearchResult(
            papers=papers,
            total_snippets=total_snippets,
            coverage_score=coverage_score,
            queries_used=limited_queries,
            latency_ms=elapsed_ms,
        )

    async def _search_weaviate(
        self,
        queries: list[str],
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
    ) -> list[PaperResult]:
        """Tier 1: Weaviate 내부 RAG 검색"""
        try:
            from app.services.rag_service import rag_service
            from app.schemas.chat import Reference

            results = []
            for query in queries:
                try:
                    retrieval_result = await rag_service.retrieve(
                        query=query,
                        year_from=year_from,
                        year_to=year_to,
                        sections=sections,
                        use_reranker=self.use_reranker,
                        min_score=self.min_relevance_score,
                    )

                    papers = self._convert_references(retrieval_result.references)
                    results.extend(papers)
                except Exception as e:
                    logger.warning(f"[Weaviate] Query '{query[:50]}...' failed: {e}")
                    continue

            return results
        except ImportError as e:
            logger.warning(f"[Weaviate] Import error: {e}")
            return []

    async def _search_epmc(
        self,
        queries: list[str],
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[PaperResult]:
        """Tier 2: Europe PMC 검색"""
        try:
            from app.services.agent.study_plan.search.europe_pmc_service import (
                europe_pmc_service,
            )

            results = []
            for query in queries:
                try:
                    epmc_result = await europe_pmc_service.search(
                        query=query,
                        max_results=self.top_k_per_query,
                        year_from=year_from,
                        year_to=year_to,
                    )

                    for paper in epmc_result.papers:
                        paper_result = PaperResult(
                            paper_id=paper.pmcid or paper.pmid or f"epmc_{uuid.uuid4().hex[:8]}",
                            title=paper.title,
                            journal=paper.journal,
                            year=paper.year,
                            snippets=[
                                SnippetResult(
                                    snippet_id=f"abstract_{paper.pmcid or paper.pmid}",
                                    paper_id=paper.pmcid or paper.pmid or "",
                                    section="abstract",
                                    text=paper.abstract[:500] if paper.abstract else "",
                                    relevance_score=0.7,  # EPMC doesn't provide scores
                                )
                            ],
                            source="epmc",
                        )
                        results.append(paper_result)
                except Exception as e:
                    logger.warning(f"[EPMC] Query '{query[:50]}...' failed: {e}")
                    continue

            return results
        except ImportError as e:
            logger.warning(f"[EPMC] Import error: {e}")
            return []

    async def _search_tavily(
        self,
        queries: list[str],
    ) -> list[PaperResult]:
        """Tier 3: Tavily 웹 검색"""
        try:
            from app.services.agent.study_plan.search.tavily_service import (
                tavily_service,
            )

            if not tavily_service.is_available:
                logger.warning("[Tavily] API key not configured")
                return []

            results = []
            for query in queries:
                try:
                    tavily_result = await tavily_service.search(
                        query=query,
                        max_results=self.top_k_per_query,
                    )

                    for item in tavily_result.results:
                        paper_result = PaperResult(
                            paper_id=f"web_{uuid.uuid4().hex[:8]}",
                            title=item.title,
                            journal=item.url,  # URL as source
                            year=0,  # Web results don't have year
                            snippets=[
                                SnippetResult(
                                    snippet_id=f"web_{uuid.uuid4().hex[:8]}",
                                    paper_id="",
                                    section="web",
                                    text=item.content[:500] if item.content else "",
                                    relevance_score=item.score,
                                )
                            ],
                            source="tavily",
                        )
                        results.append(paper_result)
                except Exception as e:
                    logger.warning(f"[Tavily] Query '{query[:50]}...' failed: {e}")
                    continue

            return results
        except ImportError as e:
            logger.warning(f"[Tavily] Import error: {e}")
            return []

    def _convert_references(
        self,
        references: list,
    ) -> list[PaperResult]:
        """Reference 목록을 PaperResult로 변환"""
        paper_snippets: dict[str, PaperResult] = {}

        for ref in references:
            # 관련성 점수 계산 (distance 기반)
            relevance = 1.0 - ref.distance if ref.distance and ref.distance <= 1.0 else 0.5

            # 최소 점수 필터
            if relevance < self.min_relevance_score:
                continue

            # 스니펫 생성
            snippet = SnippetResult(
                snippet_id=ref.chunk_id or f"snippet_{uuid.uuid4().hex[:8]}",
                paper_id=ref.paper_id,
                section=ref.section,
                text=ref.snippet,
                offset_start=ref.offset_start,
                offset_end=ref.offset_end,
                relevance_score=relevance,
                text_version=ref.text_version,
            )

            # 논문별 그룹화
            if ref.paper_id not in paper_snippets:
                paper = PaperResult(
                    paper_id=ref.paper_id,
                    title=ref.title,
                    journal=ref.journal or "",
                    year=ref.year or 0,
                    snippets=[],
                    source="weaviate",
                )
                paper_snippets[ref.paper_id] = paper

            paper_snippets[ref.paper_id].snippets.append(snippet)

        return list(paper_snippets.values())

    def _merge_results(
        self,
        paper_map: dict[str, PaperResult],
        new_papers: list[PaperResult],
    ) -> None:
        """검색 결과 병합 (중복 제거)"""
        for paper in new_papers:
            if paper.paper_id not in paper_map:
                paper_map[paper.paper_id] = paper
            else:
                # 기존 논문에 스니펫 추가 (중복 제거)
                existing = paper_map[paper.paper_id]
                seen_ids = {s.snippet_id for s in existing.snippets}
                for s in paper.snippets:
                    if s.snippet_id not in seen_ids:
                        existing.snippets.append(s)
                        seen_ids.add(s.snippet_id)

    def _calculate_coverage(
        self,
        papers: list[PaperResult],
        query_count: int,
    ) -> float:
        """검색 커버리지 점수 계산"""
        if not papers:
            return 0.0

        # 논문 수 기반 점수 (0-0.4)
        paper_score = min(len(papers) / 15, 1.0) * 0.4

        # 고품질 논문 비율 (0-0.3)
        high_quality = sum(1 for p in papers if p.max_relevance_score >= 0.7)
        quality_ratio = high_quality / len(papers) if papers else 0
        quality_score = quality_ratio * 0.3

        # 쿼리당 평균 결과 수 (0-0.3)
        avg_per_query = len(papers) / max(query_count, 1)
        query_score = min(avg_per_query / 3, 1.0) * 0.3

        return paper_score + quality_score + query_score


# 싱글톤 인스턴스
study_search_service = StudySearchService()
