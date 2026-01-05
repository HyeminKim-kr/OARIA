"""Weaviate PaperChunk 스키마 정의 및 생성

OAR-31 기반: OAR-20 스키마 설계 문서 구현
"""

import uuid
from typing import Optional

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType, Configure


# ─────────────────────────────────────────────────────────────
# 상수 정의
# ─────────────────────────────────────────────────────────────

COLLECTION_NAME = "PaperChunk"
EMBEDDING_VERSION = "openai:text-embedding-3-small:v1"


# ─────────────────────────────────────────────────────────────
# ID 생성 함수
# ─────────────────────────────────────────────────────────────

def generate_paper_id(
    pmid: str | None = None,
    pmcid: str | None = None,
    doi: str | None = None
) -> str:
    """논문 통일 ID 생성 (우선순위: pmid > pmcid > doi)"""
    if pmid:
        return f"pmid:{pmid}"
    if pmcid:
        # PMC 접두어가 있으면 제거
        clean_pmcid = pmcid.replace("PMC", "")
        return f"pmc:PMC{clean_pmcid}"
    if doi:
        return f"doi:{doi}"
    raise ValueError("최소 하나의 ID 필요 (pmid, pmcid, or doi)")


def generate_chunk_id(paper_id: str, section: str, chunk_index: int) -> str:
    """청크 고유 ID 생성"""
    return f"{paper_id}|{section}|{chunk_index}"


def generate_uuid_from_chunk_id(chunk_id: str) -> str:
    """chunk_id로 결정적 UUID 생성 (중복 방지, 재적재 용이)"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


# ─────────────────────────────────────────────────────────────
# 스키마 생성
# ─────────────────────────────────────────────────────────────

def create_paper_chunk_collection(client: weaviate.WeaviateClient) -> None:
    """PaperChunk 컬렉션 생성

    Args:
        client: Weaviate 클라이언트
    """
    # 이미 존재하면 스킵
    if client.collections.exists(COLLECTION_NAME):
        print(f"컬렉션 '{COLLECTION_NAME}'이 이미 존재합니다.")
        return

    client.collections.create(
        name=COLLECTION_NAME,
        description="암 논문 청크 데이터 (RAG 검색용)",

        # 임베딩 비활성화 (BYOV - Bring Your Own Vectors)
        vectorizer_config=Configure.Vectorizer.none(),

        # HNSW 벡터 인덱스 설정
        vector_index_config=Configure.VectorIndex.hnsw(
            distance_metric=wvc.config.VectorDistances.COSINE,
            ef_construction=128,  # 인덱스 빌드 품질
            max_connections=64,   # HNSW 그래프 연결 수
        ),

        properties=[
            # ─────────────────────────────────────
            # 내부 식별자 (운영/마이그레이션용)
            # ─────────────────────────────────────
            Property(
                name="paperId",
                data_type=DataType.TEXT,
                description="논문 통일 ID (예: pmid:12345678 또는 pmc:PMC12345678)",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="chunkId",
                data_type=DataType.TEXT,
                description="청크 고유 ID (예: pmid:12345678|methods|0)",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="embeddingVersion",
                data_type=DataType.TEXT,
                description="임베딩 모델 버전 (예: openai:text-embedding-3-small:v1)",
                index_filterable=True,
                index_searchable=False,
            ),

            # ─────────────────────────────────────
            # 외부 논문 식별자
            # ─────────────────────────────────────
            Property(
                name="pmcid",
                data_type=DataType.TEXT,
                description="PMC 고유 ID (예: PMC12345678)",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="pmid",
                data_type=DataType.TEXT,
                description="PubMed ID",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="doi",
                data_type=DataType.TEXT,
                description="DOI",
                index_filterable=True,
                index_searchable=False,
            ),

            # ─────────────────────────────────────
            # 논문 메타데이터
            # ─────────────────────────────────────
            Property(
                name="title",
                data_type=DataType.TEXT,
                description="논문 제목",
                index_filterable=False,
                index_searchable=True,  # BM25 키워드 검색
            ),
            Property(
                name="authors",
                data_type=DataType.TEXT_ARRAY,
                description="저자 목록",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="journal",
                data_type=DataType.TEXT,
                description="저널명",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="year",
                data_type=DataType.INT,
                description="출판 연도",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="keywords",
                data_type=DataType.TEXT_ARRAY,
                description="키워드 목록",
                index_filterable=True,
                index_searchable=False,
            ),

            # ─────────────────────────────────────
            # 청크 정보
            # ─────────────────────────────────────
            Property(
                name="section",
                data_type=DataType.TEXT,
                description="섹션 유형 (abstract, introduction, methods, results, discussion)",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="chunkIndex",
                data_type=DataType.INT,
                description="섹션 내 청크 순서 (0부터 시작)",
                index_filterable=True,
                index_searchable=False,
            ),
            Property(
                name="content",
                data_type=DataType.TEXT,
                description="청크 텍스트 내용 (검색 대상)",
                index_filterable=False,
                index_searchable=True,  # BM25 하이브리드 검색
            ),

            # ─────────────────────────────────────
            # 원문 위치 (재현성/감사용)
            # ─────────────────────────────────────
            Property(
                name="offsetStart",
                data_type=DataType.INT,
                description="표준 원문(canonical text)에서 시작 위치 (문자 인덱스)",
                index_filterable=False,
                index_searchable=False,
            ),
            Property(
                name="offsetEnd",
                data_type=DataType.INT,
                description="표준 원문(canonical text)에서 끝 위치 (문자 인덱스)",
                index_filterable=False,
                index_searchable=False,
            ),
            Property(
                name="textVersion",
                data_type=DataType.TEXT,
                description="표준 원문 버전 (예: canonical_v1)",
                index_filterable=True,
                index_searchable=False,
            ),

            # ─────────────────────────────────────
            # 메타 정보
            # ─────────────────────────────────────
            Property(
                name="sourceUrl",
                data_type=DataType.TEXT,
                description="원본 논문 URL",
                index_filterable=False,
                index_searchable=False,
            ),
            Property(
                name="createdAt",
                data_type=DataType.DATE,
                description="수집 일시",
                index_filterable=True,
                index_searchable=False,
            ),
        ]
    )

    print(f"✅ 컬렉션 '{COLLECTION_NAME}' 생성 완료")


def delete_paper_chunk_collection(client: weaviate.WeaviateClient) -> None:
    """PaperChunk 컬렉션 삭제 (주의: 모든 데이터 삭제됨)"""
    if client.collections.exists(COLLECTION_NAME):
        client.collections.delete(COLLECTION_NAME)
        print(f"🗑️ 컬렉션 '{COLLECTION_NAME}' 삭제 완료")
    else:
        print(f"컬렉션 '{COLLECTION_NAME}'이 존재하지 않습니다.")


def get_collection_info(client: weaviate.WeaviateClient) -> dict | None:
    """컬렉션 정보 조회"""
    if not client.collections.exists(COLLECTION_NAME):
        return None

    collection = client.collections.get(COLLECTION_NAME)
    config = collection.config.get()

    return {
        "name": config.name,
        "description": config.description,
        "properties": [
            {
                "name": prop.name,
                "data_type": str(prop.data_type),
                "index_filterable": prop.index_filterable,
                "index_searchable": prop.index_searchable,
            }
            for prop in config.properties
        ],
        "vector_index": {
            "type": str(config.vector_index_config),
        },
    }
