"""논문별 RAG 서비스

특정 논문 또는 여러 논문 내에서만 검색하는 RAG 서비스.
기존 RagService를 기반으로 paper_id 필터링 기능 추가.

사용 사례:
1. 논문 상세 페이지에서 해당 논문에 대한 질문
2. 관련 논문 포함 검색 (유사 논문 참조)
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from app.schemas.chat import Reference
from app.services.embedding_service import embedding_service
from app.services.weaviate_service import weaviate_service
from app.services.reranker_service import reranker_service


@dataclass
class PaperRetrievalResult:
    """논문별 검색 결과"""

    references: list[Reference]
    context: str  # LLM에 전달할 컨텍스트
    search_latency_ms: int
    rerank_latency_ms: int | None = None
    paper_ids_searched: list[str] | None = None  # 검색된 논문 ID들


class PaperRagService:
    """논문별 RAG 검색 서비스"""

    def __init__(
        self,
        top_k: int = 5,
        alpha: float = 0.5,
        use_reranker: bool = True,
        rerank_top_k: int = 15,
    ):
        self.top_k = top_k
        self.alpha = alpha
        self.use_reranker = use_reranker
        self.rerank_top_k = rerank_top_k

    async def retrieve_from_paper(
        self,
        paper_id: str,
        query: str,
        sections: list[str] | None = None,
        use_reranker: bool | None = None,
        min_score: float | None = None,
        collection_name: str | None = None,
    ) -> PaperRetrievalResult:
        """특정 논문 내에서만 검색

        Args:
            paper_id: 논문 ID (예: "pmc:PMC12345678")
            query: 사용자 질문
            sections: 섹션 필터 (예: ["abstract", "results"])
            use_reranker: Reranker 사용 여부
            min_score: Reranker 최소 점수 임계값
            collection_name: Weaviate 컬렉션 이름

        Returns:
            검색 결과
        """
        return await self._retrieve(
            paper_ids=[paper_id],
            query=query,
            sections=sections,
            use_reranker=use_reranker,
            min_score=min_score,
            collection_name=collection_name,
        )

    async def retrieve_with_related(
        self,
        paper_id: str,
        related_paper_ids: list[str],
        query: str,
        sections: list[str] | None = None,
        use_reranker: bool | None = None,
        min_score: float | None = None,
        collection_name: str | None = None,
    ) -> PaperRetrievalResult:
        """현재 논문 + 관련 논문에서 검색

        Args:
            paper_id: 주요 논문 ID
            related_paper_ids: 관련 논문 ID 리스트
            query: 사용자 질문
            sections: 섹션 필터
            use_reranker: Reranker 사용 여부
            min_score: Reranker 최소 점수 임계값
            collection_name: Weaviate 컬렉션 이름

        Returns:
            검색 결과
        """
        all_paper_ids = [paper_id] + related_paper_ids
        return await self._retrieve(
            paper_ids=all_paper_ids,
            query=query,
            sections=sections,
            use_reranker=use_reranker,
            min_score=min_score,
            collection_name=collection_name,
        )

    async def _retrieve(
        self,
        paper_ids: list[str],
        query: str,
        sections: list[str] | None = None,
        use_reranker: bool | None = None,
        min_score: float | None = None,
        collection_name: str | None = None,
    ) -> PaperRetrievalResult:
        """내부 검색 로직

        Args:
            paper_ids: 검색할 논문 ID 리스트
            query: 사용자 질문
            sections: 섹션 필터
            use_reranker: Reranker 사용 여부
            min_score: Reranker 최소 점수 임계값
            collection_name: Weaviate 컬렉션 이름

        Returns:
            검색 결과
        """
        start = time.perf_counter()
        rerank_latency_ms = None

        logger.info(f"[PaperRAG] Starting retrieval for papers={paper_ids}, query='{query[:50]}...'")

        # 컬렉션 이름 저장 (Parent Retrieval에서 사용)
        self._current_collection_name = collection_name

        # Reranker 사용 여부 결정
        should_rerank = use_reranker if use_reranker is not None else self.use_reranker
        should_rerank = should_rerank and reranker_service.is_enabled
        logger.debug(f"[PaperRAG] Reranker enabled: {should_rerank}")

        # 1. 쿼리 임베딩
        embed_start = time.perf_counter()
        query_vector = await embedding_service.embed_text(query)
        embed_ms = int((time.perf_counter() - embed_start) * 1000)
        logger.info(f"[PaperRAG] Step 1/4 Embedding: {embed_ms}ms")

        # 2. 논문 필터링 검색
        search_start = time.perf_counter()
        search_limit = self.rerank_top_k if should_rerank else self.top_k

        if len(paper_ids) == 1:
            # 단일 논문 검색 (비동기 래퍼 사용)
            search_results = await weaviate_service.search_hybrid_by_paper_async(
                paper_id=paper_ids[0],
                query=query,
                query_vector=query_vector,
                limit=search_limit,
                alpha=self.alpha,
                sections=sections,
                collection_name=collection_name,
            )
        else:
            # 여러 논문 검색 (비동기 래퍼 사용)
            search_results = await weaviate_service.search_hybrid_by_papers_async(
                paper_ids=paper_ids,
                query=query,
                query_vector=query_vector,
                limit=search_limit,
                alpha=self.alpha,
                sections=sections,
                collection_name=collection_name,
            )
        search_ms = int((time.perf_counter() - search_start) * 1000)
        logger.info(f"[PaperRAG] Step 2/4 Weaviate search: {search_ms}ms, found {len(search_results)} results")

        # 3. Reranker로 재정렬
        if should_rerank and search_results:
            rerank_start = time.perf_counter()

            rerank_results = reranker_service.rerank(
                query=query,
                documents=search_results,
                content_key="content",
                top_k=self.top_k,
                min_score=min_score,
            )

            search_results = []
            for rr in rerank_results:
                doc = rr.document.copy()
                doc["rerank_score"] = rr.score
                doc["original_score"] = doc.get("score", 0)
                doc["score"] = rr.score
                search_results.append(doc)

            rerank_latency_ms = int((time.perf_counter() - rerank_start) * 1000)
            logger.info(f"[PaperRAG] Step 3/4 Rerank: {rerank_latency_ms}ms, kept {len(search_results)} results")
        else:
            logger.info(f"[PaperRAG] Step 3/4 Rerank: skipped (enabled={should_rerank}, results={len(search_results)})")

        # 4. Parent Retrieval
        parent_start = time.perf_counter()
        references, context = await self._expand_to_parent_sections_async(search_results)
        parent_ms = int((time.perf_counter() - parent_start) * 1000)
        logger.info(f"[PaperRAG] Step 4/4 Parent retrieval: {parent_ms}ms, refs={len(references)}")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(f"[PaperRAG] Total retrieval: {elapsed_ms}ms (embed={embed_ms}, search={search_ms}, rerank={rerank_latency_ms or 0}, parent={parent_ms})")

        return PaperRetrievalResult(
            references=references,
            context=context,
            search_latency_ms=elapsed_ms,
            rerank_latency_ms=rerank_latency_ms,
            paper_ids_searched=paper_ids,
        )

    async def _expand_to_parent_sections_async(
        self,
        search_results: list[dict[str, Any]],
    ) -> tuple[list[Reference], str]:
        """검색된 청크를 부모 섹션으로 확장 (비동기)"""
        seen_sections: set[tuple[str, str]] = set()
        unique_results = []

        for result in search_results:
            key = (result["paperId"], result["section"])
            if key not in seen_sections:
                seen_sections.add(key)
                unique_results.append(result)

        references = []
        context_parts = []

        for idx, result in enumerate(unique_results, 1):
            paper_id = result["paperId"]
            section = result["section"]

            # 비동기 래퍼 사용
            section_chunks = await weaviate_service.get_chunks_by_paper_and_section_async(
                paper_id=paper_id,
                section=section,
                collection_name=getattr(self, "_current_collection_name", None),
            )

            if not section_chunks:
                continue

            section_text = self._combine_chunks(section_chunks)

            first_chunk = section_chunks[0]
            matched_offset_start = int(result.get("offsetStart") or 0)
            matched_offset_end = int(result.get("offsetEnd") or 0)
            matched_content = result.get("content", "")

            ref = Reference(
                paper_id=paper_id,
                chunk_id=result.get("chunkId", first_chunk.get("chunkId", "")),
                title=first_chunk.get("title", ""),
                journal=first_chunk.get("journal"),
                year=first_chunk.get("year"),
                section=section,
                snippet=matched_content[:500] + "..." if len(matched_content) > 500 else matched_content,
                offset_start=matched_offset_start,
                offset_end=matched_offset_end,
                text_version=first_chunk.get("textVersion", "v1"),
                distance=result.get("score", result.get("distance", 0.0)),
            )
            references.append(ref)

            context_parts.append(
                f"[{idx}] {ref.title} ({ref.journal}, {ref.year}) - {section}\n"
                f"{section_text}\n"
            )

        context = "\n---\n\n".join(context_parts)

        return references, context

    def _combine_chunks(self, chunks: list[dict[str, Any]]) -> str:
        """청크들을 합쳐서 전체 섹션 텍스트 생성"""
        if not chunks:
            return ""

        if len(chunks) == 1:
            return chunks[0].get("content", "")

        combined = chunks[0].get("content", "")

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]

            prev_end = int(prev_chunk.get("offsetEnd") or 0)
            curr_start = int(curr_chunk.get("offsetStart") or 0)
            curr_content = curr_chunk.get("content", "")

            if curr_start < prev_end:
                overlap_size = prev_end - curr_start
                curr_content = curr_content[overlap_size:]

            combined += curr_content

        return combined


# 싱글톤 인스턴스
paper_rag_service = PaperRagService()


def get_paper_rag_service() -> PaperRagService:
    """PaperRagService 의존성"""
    return paper_rag_service
