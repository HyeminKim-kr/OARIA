"""Weaviate 클라이언트 및 데이터 삽입 유틸리티

OAR-31 기반
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

import weaviate
import weaviate.classes as wvc
from weaviate.classes.query import Filter, MetadataQuery

from .schema import (
    COLLECTION_NAME,
    generate_uuid_from_chunk_id,
)
from .embeddings import EmbeddingClient

# 타입 힌트용 (순환 참조 방지)
if TYPE_CHECKING:
    from ..chunker import Chunk, ChunkingResult


class WeaviateClient:
    """Weaviate PaperChunk 클라이언트"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        embedding_client: Optional[EmbeddingClient] = None,
    ):
        """
        Args:
            host: Weaviate 호스트
            port: Weaviate 포트
            embedding_client: 임베딩 클라이언트 (None이면 자동 생성)
        """
        self.client = weaviate.connect_to_local(host=host, port=port)
        self.embedding_client = embedding_client or EmbeddingClient()
        self._collection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """연결 종료"""
        if self.client:
            self.client.close()

    @property
    def collection(self):
        """PaperChunk 컬렉션 반환"""
        if self._collection is None:
            self._collection = self.client.collections.get(COLLECTION_NAME)
        return self._collection

    # ─────────────────────────────────────────────────────────────
    # 데이터 삽입
    # ─────────────────────────────────────────────────────────────

    def insert_chunk(
        self,
        chunk,  # Chunk 객체
        paper_metadata: dict,
        embedding: Optional[list[float]] = None,
    ) -> str:
        """단일 청크 삽입

        Args:
            chunk: Chunk 객체 (chunker 모듈 결과)
            paper_metadata: 논문 메타데이터 (pmcid, pmid, doi, title, authors, journal, year, keywords, sourceUrl)
            embedding: 임베딩 벡터 (None이면 자동 생성)

        Returns:
            생성된 UUID
        """
        # 임베딩 생성
        if embedding is None:
            embedding = self.embedding_client.embed_text(chunk.embedding_input)

        # UUID 생성
        object_uuid = generate_uuid_from_chunk_id(chunk.chunk_id)

        # 속성 구성
        properties = {
            "paperId": chunk.paper_id,
            "chunkId": chunk.chunk_id,
            "embeddingVersion": self.embedding_client.get_version_string(),
            "pmcid": paper_metadata.get("pmcid"),
            "pmid": paper_metadata.get("pmid"),
            "doi": paper_metadata.get("doi"),
            "title": paper_metadata.get("title", ""),
            "authors": paper_metadata.get("authors", []),
            "journal": paper_metadata.get("journal"),
            "year": paper_metadata.get("year"),
            "keywords": paper_metadata.get("keywords", []),
            "section": chunk.section,
            "chunkIndex": chunk.chunk_index,
            "content": chunk.text,
            "offsetStart": chunk.offset_start,
            "offsetEnd": chunk.offset_end,
            "textVersion": chunk.text_version,
            "sourceUrl": paper_metadata.get("sourceUrl"),
            "createdAt": datetime.now(timezone.utc),
        }

        # 삽입
        self.collection.data.insert(
            uuid=object_uuid,
            properties=properties,
            vector=embedding,
        )

        return object_uuid

    def insert_chunking_result(
        self,
        result,  # ChunkingResult 객체
        paper_metadata: dict,
        batch_size: int = 10,
    ) -> list[str]:
        """청킹 결과 전체 삽입

        Args:
            result: ChunkingResult 객체 (chunker 모듈 결과)
            paper_metadata: 논문 메타데이터
            batch_size: 배치 임베딩 크기

        Returns:
            생성된 UUID 리스트
        """
        uuids = []
        chunks = result.chunks

        # 배치 임베딩 생성
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_texts = [c.embedding_input for c in batch_chunks]
            batch_embeddings = self.embedding_client.embed_texts(batch_texts)

            # 삽입
            for chunk, embedding in zip(batch_chunks, batch_embeddings):
                uuid = self.insert_chunk(chunk, paper_metadata, embedding)
                uuids.append(uuid)

        return uuids

    # ─────────────────────────────────────────────────────────────
    # 검색
    # ─────────────────────────────────────────────────────────────

    def search_by_vector(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Filter] = None,
    ) -> list[dict]:
        """벡터 유사도 검색

        Args:
            query: 검색 쿼리 텍스트
            limit: 결과 개수
            filters: 필터 조건

        Returns:
            검색 결과 리스트
        """
        query_vector = self.embedding_client.embed_text(query)

        response = self.collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(distance=True),
        )

        return [
            {
                "uuid": str(obj.uuid),
                "distance": obj.metadata.distance,
                "properties": dict(obj.properties),
            }
            for obj in response.objects
        ]

    def search_hybrid(
        self,
        query: str,
        limit: int = 5,
        alpha: float = 0.5,
        filters: Optional[Filter] = None,
    ) -> list[dict]:
        """하이브리드 검색 (벡터 + 키워드)

        Args:
            query: 검색 쿼리 텍스트
            limit: 결과 개수
            alpha: 벡터/키워드 비중 (0=키워드, 1=벡터, 0.5=균형)
            filters: 필터 조건

        Returns:
            검색 결과 리스트
        """
        query_vector = self.embedding_client.embed_text(query)

        response = self.collection.query.hybrid(
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
                "properties": dict(obj.properties),
            }
            for obj in response.objects
        ]

    def search_by_keyword(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Filter] = None,
    ) -> list[dict]:
        """키워드 검색 (BM25)

        Args:
            query: 검색 쿼리 텍스트
            limit: 결과 개수
            filters: 필터 조건

        Returns:
            검색 결과 리스트
        """
        response = self.collection.query.bm25(
            query=query,
            limit=limit,
            filters=filters,
            return_metadata=MetadataQuery(score=True),
        )

        return [
            {
                "uuid": str(obj.uuid),
                "score": obj.metadata.score,
                "properties": dict(obj.properties),
            }
            for obj in response.objects
        ]

    # ─────────────────────────────────────────────────────────────
    # 조회
    # ─────────────────────────────────────────────────────────────

    def get_by_paper_id(self, paper_id: str) -> list[dict]:
        """논문 ID로 모든 청크 조회

        Args:
            paper_id: 논문 ID (예: pmc:PMC12345678)

        Returns:
            청크 리스트
        """
        response = self.collection.query.fetch_objects(
            filters=Filter.by_property("paperId").equal(paper_id),
            sort=wvc.query.Sort.by_property("chunkIndex", ascending=True),
        )

        return [dict(obj.properties) for obj in response.objects]

    def get_by_chunk_id(self, chunk_id: str) -> Optional[dict]:
        """청크 ID로 단일 청크 조회

        Args:
            chunk_id: 청크 ID (예: pmc:PMC12345678|abstract|0)

        Returns:
            청크 데이터 또는 None
        """
        response = self.collection.query.fetch_objects(
            filters=Filter.by_property("chunkId").equal(chunk_id),
            limit=1,
        )

        if response.objects:
            return dict(response.objects[0].properties)
        return None

    def count_objects(self) -> int:
        """컬렉션 내 객체 수 반환"""
        response = self.collection.aggregate.over_all(total_count=True)
        return response.total_count

    # ─────────────────────────────────────────────────────────────
    # 삭제
    # ─────────────────────────────────────────────────────────────

    def delete_by_paper_id(self, paper_id: str) -> int:
        """논문 ID로 모든 청크 삭제

        Args:
            paper_id: 논문 ID

        Returns:
            삭제된 객체 수
        """
        result = self.collection.data.delete_many(
            where=Filter.by_property("paperId").equal(paper_id)
        )
        return result.successful
