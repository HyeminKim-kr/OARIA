"""Study Plan Agent 전용 검색 서비스

기존 RAG 서비스를 활용하여 에이전트에 최적화된 검색을 제공합니다.
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from app.services.rag_service import rag_service, RetrievalResult
from app.schemas.chat import Reference

from .types import SearchResult, PaperResult, SnippetResult

logger = logging.getLogger(__name__)


class StudySearchService:
    """Study Plan Agent 전용 검색 서비스"""

    def __init__(
        self,
        top_k_per_query: int = 5,
        max_queries: int = 8,
        use_reranker: bool = True,
        min_relevance_score: float = 0.3,
    ):
        self.top_k_per_query = top_k_per_query
        self.max_queries = max_queries
        self.use_reranker = use_reranker
        self.min_relevance_score = min_relevance_score

    async def search_studies(
        self,
        queries: list[str],
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
    ) -> SearchResult:
        """다중 쿼리로 논문 검색

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
        logger.info(f"Searching with {len(limited_queries)} queries")

        # 병렬 검색 실행
        results = await asyncio.gather(
            *[
                self._search_single_query(
                    query=q,
                    year_from=year_from,
                    year_to=year_to,
                    sections=sections,
                )
                for q in limited_queries
            ],
            return_exceptions=True,
        )

        # 결과 집계
        paper_map: dict[str, PaperResult] = {}
        total_snippets = 0

        for query, result in zip(limited_queries, results):
            if isinstance(result, Exception):
                logger.warning(f"Query '{query[:50]}...' failed: {result}")
                continue

            for paper, snippets in result:
                if paper.paper_id not in paper_map:
                    paper_map[paper.paper_id] = paper
                else:
                    # 기존 논문에 스니펫 추가 (중복 제거)
                    existing = paper_map[paper.paper_id]
                    seen_ids = {s.snippet_id for s in existing.snippets}
                    for s in snippets:
                        if s.snippet_id not in seen_ids:
                            existing.snippets.append(s)
                            seen_ids.add(s.snippet_id)

                total_snippets += len(snippets)

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
            f"Search completed: {len(papers)} papers, "
            f"{total_snippets} snippets, coverage={coverage_score:.2f}, "
            f"latency={elapsed_ms}ms"
        )

        return SearchResult(
            papers=papers,
            total_snippets=total_snippets,
            coverage_score=coverage_score,
            queries_used=limited_queries,
            latency_ms=elapsed_ms,
        )

    async def search_for_evidence(
        self,
        queries: list[str],
        target_sections: list[str] | None = None,
    ) -> SearchResult:
        """Evidence 추출용 검색

        Methods, Results 섹션에 집중하여 검색합니다.
        """
        sections = target_sections or ["methods", "results"]
        return await self.search_studies(queries=queries, sections=sections)

    async def search_for_methodology(
        self,
        queries: list[str],
    ) -> SearchResult:
        """방법론 분석용 검색

        Methods 섹션에 집중하여 검색합니다.
        """
        return await self.search_studies(queries=queries, sections=["methods"])

    async def _search_single_query(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
    ) -> list[tuple[PaperResult, list[SnippetResult]]]:
        """단일 쿼리 검색"""
        try:
            result: RetrievalResult = await rag_service.retrieve(
                query=query,
                year_from=year_from,
                year_to=year_to,
                sections=sections,
                use_reranker=self.use_reranker,
                min_score=self.min_relevance_score,
            )

            return self._convert_references(result.references)

        except Exception as e:
            logger.error(f"Error searching query '{query[:50]}...': {e}")
            return []

    def _convert_references(
        self,
        references: list[Reference],
    ) -> list[tuple[PaperResult, list[SnippetResult]]]:
        """Reference 목록을 PaperResult로 변환"""
        paper_snippets: dict[str, tuple[PaperResult, list[SnippetResult]]] = {}

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
                )
                paper_snippets[ref.paper_id] = (paper, [])

            paper_snippets[ref.paper_id][1].append(snippet)
            paper_snippets[ref.paper_id][0].snippets.append(snippet)

        return list(paper_snippets.values())

    def _calculate_coverage(
        self,
        papers: list[PaperResult],
        query_count: int,
    ) -> float:
        """검색 커버리지 점수 계산

        - 논문 수
        - 고품질 논문 비율
        - 쿼리당 결과 수
        """
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
