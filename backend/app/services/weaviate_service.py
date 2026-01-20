"""Weaviate 검색 서비스

Batch 모듈의 WeaviateClient를 Backend용으로 포팅
- 검색 기능만 포함 (삽입/삭제는 batch에서 처리)
- 동기 클라이언트 (Weaviate Python SDK가 비동기 미지원)
- 멀티 컬렉션 지원 (프로덕션 + 샘플 임베딩)
- 비동기 래퍼 제공 (asyncio.to_thread 사용)
"""

import asyncio
import logging
import time
from typing import Any

import weaviate
from weaviate.classes.query import Filter, MetadataQuery

from app.config import settings

logger = logging.getLogger(__name__)


# 기본 프로덕션 컬렉션
DEFAULT_COLLECTION_NAME = "PaperChunk"


class WeaviateService:
    """Weaviate 검색 서비스"""

    _instance: "WeaviateService | None" = None
    _client: weaviate.WeaviateClient | None = None

    def __new__(cls) -> "WeaviateService":
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> weaviate.WeaviateClient:
        """Weaviate 클라이언트 반환 (지연 초기화)"""
        if self._client is None:
            start = time.perf_counter()
            self._client = weaviate.connect_to_local(
                host=settings.weaviate_host,
                port=settings.weaviate_port,
            )
            connect_ms = int((time.perf_counter() - start) * 1000)
            logger.info(f"[Weaviate] Connected to {settings.weaviate_host}:{settings.weaviate_port} in {connect_ms}ms")
        return self._client

    @property
    def collection(self):
        """기본 PaperChunk 컬렉션 반환 (하위 호환성)"""
        return self._get_client().collections.get(DEFAULT_COLLECTION_NAME)

    def get_collection(self, collection_name: str | None = None):
        """컬렉션 반환 (이름 지정 가능)

        Args:
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            Weaviate 컬렉션
        """
        name = collection_name or DEFAULT_COLLECTION_NAME
        return self._get_client().collections.get(name)

    def collection_exists(self, collection_name: str) -> bool:
        """컬렉션 존재 여부 확인"""
        try:
            client = self._get_client()
            return client.collections.exists(collection_name)
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """모든 컬렉션 목록 반환"""
        try:
            client = self._get_client()
            return [col.name for col in client.collections.list_all()]
        except Exception:
            return []

    def get_collection_stats(self, collection_name: str | None = None) -> dict[str, Any]:
        """컬렉션 통계 조회

        Args:
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            컬렉션 통계 (객체 수 등)
        """
        try:
            col = self.get_collection(collection_name)
            aggregate = col.aggregate.over_all()
            return {
                "collection_name": collection_name or DEFAULT_COLLECTION_NAME,
                "total_objects": aggregate.total_count,
            }
        except Exception as e:
            return {
                "collection_name": collection_name or DEFAULT_COLLECTION_NAME,
                "error": str(e),
            }

    def close(self):
        """연결 종료"""
        if self._client:
            self._client.close()
            self._client = None

    # ─────────────────────────────────────────────────────────────
    # 검색
    # ─────────────────────────────────────────────────────────────

    def search_by_vector(
        self,
        query_vector: list[float],
        limit: int = 5,
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """벡터 유사도 검색

        Args:
            query_vector: 쿼리 임베딩 벡터
            limit: 결과 개수
            year_from: 연도 필터 (이상)
            year_to: 연도 필터 (이하)
            sections: 섹션 필터
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            검색 결과 리스트
        """
        filters = self._build_filters(year_from, year_to, sections)
        col = self.get_collection(collection_name)

        response = col.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(distance=True),
        )

        return [
            {
                "uuid": str(obj.uuid),
                "distance": obj.metadata.distance,
                **dict(obj.properties),
            }
            for obj in response.objects
        ]

    def search_hybrid(
        self,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        alpha: float = 0.5,
        year_from: int | None = None,
        year_to: int | None = None,
        sections: list[str] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """하이브리드 검색 (벡터 + 키워드)

        Args:
            query: 검색 쿼리 텍스트
            query_vector: 쿼리 임베딩 벡터
            limit: 결과 개수
            alpha: 벡터/키워드 비중 (0=키워드, 1=벡터, 0.5=균형)
            year_from: 연도 필터 (이상)
            year_to: 연도 필터 (이하)
            sections: 섹션 필터
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            검색 결과 리스트
        """
        filters = self._build_filters(year_from, year_to, sections)
        col = self.get_collection(collection_name)

        response = col.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(score=True),
        )

        return [
            {
                "uuid": str(obj.uuid),
                "score": obj.metadata.score,
                **dict(obj.properties),
            }
            for obj in response.objects
        ]

    def search_hybrid_by_paper(
        self,
        paper_id: str,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        alpha: float = 0.5,
        sections: list[str] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """특정 논문 내에서만 하이브리드 검색

        Args:
            paper_id: 논문 ID (예: "pmc:PMC12345678")
            query: 검색 쿼리 텍스트
            query_vector: 쿼리 임베딩 벡터
            limit: 결과 개수
            alpha: 벡터/키워드 비중 (0=키워드, 1=벡터, 0.5=균형)
            sections: 섹션 필터
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            검색 결과 리스트
        """
        # paper_id 필터
        filters = Filter.by_property("paperId").equal(paper_id)

        # 섹션 필터 추가
        if sections:
            section_filters = [
                Filter.by_property("section").equal(s) for s in sections
            ]
            if len(section_filters) == 1:
                filters = filters & section_filters[0]
            else:
                combined = section_filters[0]
                for f in section_filters[1:]:
                    combined = combined | f
                filters = filters & combined

        col = self.get_collection(collection_name)

        response = col.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(score=True),
        )

        return [
            {
                "uuid": str(obj.uuid),
                "score": obj.metadata.score,
                **dict(obj.properties),
            }
            for obj in response.objects
        ]

    def search_hybrid_by_papers(
        self,
        paper_ids: list[str],
        query: str,
        query_vector: list[float],
        limit: int = 5,
        alpha: float = 0.5,
        sections: list[str] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """여러 논문에서 하이브리드 검색

        Args:
            paper_ids: 논문 ID 리스트
            query: 검색 쿼리 텍스트
            query_vector: 쿼리 임베딩 벡터
            limit: 결과 개수
            alpha: 벡터/키워드 비중
            sections: 섹션 필터
            collection_name: 컬렉션 이름

        Returns:
            검색 결과 리스트
        """
        if not paper_ids:
            return []

        # 논문 ID 필터 (OR)
        paper_filters = [Filter.by_property("paperId").equal(pid) for pid in paper_ids]
        if len(paper_filters) == 1:
            filters = paper_filters[0]
        else:
            filters = paper_filters[0]
            for f in paper_filters[1:]:
                filters = filters | f

        # 섹션 필터 추가
        if sections:
            section_filters = [
                Filter.by_property("section").equal(s) for s in sections
            ]
            if len(section_filters) == 1:
                section_filter = section_filters[0]
            else:
                section_filter = section_filters[0]
                for f in section_filters[1:]:
                    section_filter = section_filter | f
            filters = filters & section_filter

        col = self.get_collection(collection_name)

        response = col.query.hybrid(
            query=query,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(score=True),
        )

        return [
            {
                "uuid": str(obj.uuid),
                "score": obj.metadata.score,
                **dict(obj.properties),
            }
            for obj in response.objects
        ]

    # ─────────────────────────────────────────────────────────────
    # 조회
    # ─────────────────────────────────────────────────────────────

    def get_chunks_by_paper_and_section(
        self,
        paper_id: str,
        section: str,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """논문 ID와 섹션으로 모든 청크 조회 (Parent Retrieval용)

        Args:
            paper_id: 논문 ID
            section: 섹션명
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            청크 리스트 (chunkIndex 순)
        """
        filters = (
            Filter.by_property("paperId").equal(paper_id)
            & Filter.by_property("section").equal(section)
        )
        col = self.get_collection(collection_name)

        response = col.query.fetch_objects(
            filters=filters,
            limit=100,  # 한 섹션의 최대 청크 수
        )

        # chunkIndex로 정렬
        chunks = [dict(obj.properties) for obj in response.objects]
        chunks.sort(key=lambda x: x.get("chunkIndex", 0))

        return chunks

    def get_by_paper_id(
        self,
        paper_id: str,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """논문 ID로 모든 청크 조회

        Args:
            paper_id: 논문 ID
            collection_name: 컬렉션 이름 (None이면 기본 컬렉션)

        Returns:
            청크 리스트
        """
        col = self.get_collection(collection_name)
        response = col.query.fetch_objects(
            filters=Filter.by_property("paperId").equal(paper_id),
            limit=500,
        )

        chunks = [dict(obj.properties) for obj in response.objects]
        chunks.sort(key=lambda x: x.get("chunkIndex", 0))

        return chunks

    # ─────────────────────────────────────────────────────────────
    # 헬퍼
    # ─────────────────────────────────────────────────────────────

    def _build_filters(
        self,
        year_from: int | None,
        year_to: int | None,
        sections: list[str] | None,
    ) -> Filter | None:
        """필터 조건 생성"""
        conditions = []

        if year_from is not None:
            conditions.append(Filter.by_property("year").greater_or_equal(year_from))
        if year_to is not None:
            conditions.append(Filter.by_property("year").less_or_equal(year_to))
        if sections:
            # OR 조건으로 섹션 필터
            section_filters = [
                Filter.by_property("section").equal(s) for s in sections
            ]
            if len(section_filters) == 1:
                conditions.append(section_filters[0])
            else:
                # 여러 섹션은 OR로 연결
                combined = section_filters[0]
                for f in section_filters[1:]:
                    combined = combined | f
                conditions.append(combined)

        if not conditions:
            return None

        # AND로 모든 조건 연결
        result = conditions[0]
        for c in conditions[1:]:
            result = result & c

        return result

    # ─────────────────────────────────────────────────────────────
    # 비동기 래퍼 (async context에서 블로킹 방지)
    # ─────────────────────────────────────────────────────────────

    async def search_hybrid_by_paper_async(
        self,
        paper_id: str,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        alpha: float = 0.5,
        sections: list[str] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """특정 논문 내 하이브리드 검색 (비동기 래퍼)"""
        return await asyncio.to_thread(
            self.search_hybrid_by_paper,
            paper_id,
            query,
            query_vector,
            limit,
            alpha,
            sections,
            collection_name,
        )

    async def search_hybrid_by_papers_async(
        self,
        paper_ids: list[str],
        query: str,
        query_vector: list[float],
        limit: int = 5,
        alpha: float = 0.5,
        sections: list[str] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """여러 논문 내 하이브리드 검색 (비동기 래퍼)"""
        return await asyncio.to_thread(
            self.search_hybrid_by_papers,
            paper_ids,
            query,
            query_vector,
            limit,
            alpha,
            sections,
            collection_name,
        )

    async def get_chunks_by_paper_and_section_async(
        self,
        paper_id: str,
        section: str,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """논문 ID와 섹션으로 청크 조회 (비동기 래퍼)"""
        return await asyncio.to_thread(
            self.get_chunks_by_paper_and_section,
            paper_id,
            section,
            collection_name,
        )


# 싱글톤 인스턴스
weaviate_service = WeaviateService()


def get_weaviate_service() -> WeaviateService:
    """Weaviate 서비스 의존성"""
    return weaviate_service
