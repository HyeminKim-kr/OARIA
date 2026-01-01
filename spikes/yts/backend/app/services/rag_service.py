"""RAG 서비스

Parent Retrieval 패턴:
1. 작은 청크로 벡터 검색 (정밀한 의미 매칭)
2. 검색된 청크의 부모 섹션 전체를 가져옴 (완전한 문맥)
3. LLM에 전체 섹션 컨텍스트 제공

참고: spikes/yts/docs/backend/retrieval-strategy.md
"""

from dataclasses import dataclass
from typing import Any

from app.schemas.chat import Reference
from app.services.embedding_service import embedding_service
from app.services.weaviate_service import weaviate_service


@dataclass
class RetrievalResult:
    """검색 결과"""

    references: list[Reference]
    context: str  # LLM에 전달할 컨텍스트
    search_latency_ms: int


class RagService:
    """RAG 검색 서비스"""

    def __init__(
        self,
        top_k: int = 5,
        alpha: float = 0.5,  # 하이브리드 검색 비중
    ):
        self.top_k = top_k
        self.alpha = alpha

    def retrieve(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
    ) -> RetrievalResult:
        """질문에 대한 관련 문서 검색

        Args:
            query: 사용자 질문
            year_from: 연도 필터 (이상)
            year_to: 연도 필터 (이하)
            sections: 섹션 필터

        Returns:
            검색 결과 (참조 목록, 컨텍스트, 지연시간)
        """
        import time

        start = time.perf_counter()

        # 1. 쿼리 임베딩
        query_vector = embedding_service.embed_text(query)

        # 2. 하이브리드 검색 (청크 단위)
        search_results = weaviate_service.search_hybrid(
            query=query,
            query_vector=query_vector,
            limit=self.top_k,
            alpha=self.alpha,
            year_from=year_from,
            year_to=year_to,
            sections=sections,
        )

        # 3. Parent Retrieval: 검색된 청크의 섹션 전체 가져오기
        references, context = self._expand_to_parent_sections(search_results)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return RetrievalResult(
            references=references,
            context=context,
            search_latency_ms=elapsed_ms,
        )

    def _expand_to_parent_sections(
        self,
        search_results: list[dict[str, Any]],
    ) -> tuple[list[Reference], str]:
        """검색된 청크를 부모 섹션으로 확장

        Args:
            search_results: 벡터 검색 결과

        Returns:
            (참조 목록, 전체 컨텍스트 텍스트)
        """
        # 중복 제거: (paperId, section) 쌍으로 그룹화
        seen_sections: set[tuple[str, str]] = set()
        unique_results = []

        for result in search_results:
            key = (result["paperId"], result["section"])
            if key not in seen_sections:
                seen_sections.add(key)
                unique_results.append(result)

        # 각 고유 섹션에 대해 전체 청크 가져오기
        references = []
        context_parts = []

        for idx, result in enumerate(unique_results, 1):
            paper_id = result["paperId"]
            section = result["section"]

            # 섹션의 모든 청크 가져오기
            section_chunks = weaviate_service.get_chunks_by_paper_and_section(
                paper_id=paper_id,
                section=section,
            )

            if not section_chunks:
                continue

            # 청크들을 합쳐서 전체 섹션 텍스트 생성
            section_text = self._combine_chunks(section_chunks)

            # Reference 생성
            first_chunk = section_chunks[0]
            ref = Reference(
                paper_id=paper_id,
                chunk_id=first_chunk.get("chunkId", ""),
                title=first_chunk.get("title", ""),
                journal=first_chunk.get("journal"),
                year=first_chunk.get("year"),
                section=section,
                snippet=section_text[:500] + "..." if len(section_text) > 500 else section_text,
                offset_start=first_chunk.get("offsetStart", 0),
                offset_end=section_chunks[-1].get("offsetEnd", 0),
                text_version=first_chunk.get("textVersion", "v1"),
                distance=result.get("score", result.get("distance", 0.0)),
            )
            references.append(ref)

            # 컨텍스트 포맷팅
            context_parts.append(
                f"[{idx}] {ref.title} ({ref.journal}, {ref.year}) - {section}\n"
                f"{section_text}\n"
            )

        context = "\n---\n\n".join(context_parts)

        return references, context

    def _combine_chunks(self, chunks: list[dict[str, Any]]) -> str:
        """청크들을 합쳐서 전체 섹션 텍스트 생성

        청크 간 overlap 제거하여 자연스러운 텍스트 생성
        """
        if not chunks:
            return ""

        if len(chunks) == 1:
            return chunks[0].get("content", "")

        # 첫 청크는 전체 사용
        combined = chunks[0].get("content", "")

        # 이후 청크들은 overlap 고려하여 추가
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]

            prev_end = prev_chunk.get("offsetEnd", 0)
            curr_start = curr_chunk.get("offsetStart", 0)
            curr_content = curr_chunk.get("content", "")

            # overlap이 있으면 겹치는 부분 제거
            if curr_start < prev_end:
                overlap_size = prev_end - curr_start
                # 문자 단위 offset이므로 직접 슬라이싱
                curr_content = curr_content[overlap_size:]

            combined += curr_content

        return combined


# 싱글톤 인스턴스
rag_service = RagService()


def get_rag_service() -> RagService:
    """RAG 서비스 의존성"""
    return rag_service
