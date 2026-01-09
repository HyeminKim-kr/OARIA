"""샘플 임베딩 태스크

샘플 쿼리에 연결된 논문들을 선택된 청킹/임베딩 전략으로 처리하여
별도의 Weaviate 컬렉션에 저장합니다.

흐름:
1. sample_embeddings 레코드 조회
2. 상태를 'processing'으로 업데이트
3. 해당 샘플 쿼리로 수집된 논문 조회
4. Weaviate 컬렉션 생성 (없으면)
5. 논문별 청킹 + 임베딩 + 저장 (병렬 처리)
6. 상태를 'completed'로 업데이트 (또는 'failed')
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

import psycopg
import structlog
import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType, Configure
from psycopg_pool import ConnectionPool

from ..celery_app import app
from ..config import settings
from ..storage import S3Storage
from ..rag import get_chunker as rag_get_chunker, get_embedder as rag_get_embedder

# 병렬 처리 설정 (OpenAI rate limit 고려)
# - OpenAI embedding: 3,000 RPM, 1,000,000 TPM
# - 논문당 ~30청크, 배치 10개씩 = ~3 requests/paper
# - 5 workers × 3 requests = ~15 requests 동시 (안전 범위)
MAX_WORKERS = 5  # 동시 처리 논문 수
PROGRESS_UPDATE_INTERVAL = 5  # N개 논문 처리 후 progress 업데이트

logger = structlog.get_logger()


# ============================================================
# Connection Pool (재사용)
# ============================================================

_db_pool: ConnectionPool | None = None


def get_db_pool() -> ConnectionPool:
    """Connection Pool 획득 (싱글톤)"""
    global _db_pool
    if _db_pool is None:
        _db_pool = ConnectionPool(
            conninfo=settings.db.dsn,
            min_size=2,
            max_size=10,
            open=True,
        )
        logger.info("sample_embed_db_pool_created", min_size=2, max_size=10)
    return _db_pool


# ============================================================
# Weaviate 컬렉션 관리
# ============================================================


def get_weaviate_client():
    """Weaviate 클라이언트 생성"""
    return weaviate.connect_to_local(
        host=settings.weaviate.host,
        port=settings.weaviate.port,
    )


def create_sample_collection(client, collection_name: str) -> None:
    """샘플 임베딩용 컬렉션 생성

    기본 PaperChunk와 동일한 스키마를 사용합니다.
    """
    if client.collections.exists(collection_name):
        logger.info("collection_exists", collection_name=collection_name)
        return

    client.collections.create(
        name=collection_name,
        description=f"샘플 임베딩 컬렉션 - {collection_name}",
        vectorizer_config=Configure.Vectorizer.none(),
        vector_index_config=Configure.VectorIndex.hnsw(
            distance_metric=wvc.config.VectorDistances.COSINE,
            ef_construction=128,
            max_connections=64,
        ),
        properties=[
            Property(name="paperId", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="chunkId", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="embeddingVersion", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="pmcid", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="pmid", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="doi", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="title", data_type=DataType.TEXT, index_filterable=False, index_searchable=True),
            Property(name="authors", data_type=DataType.TEXT_ARRAY, index_filterable=True, index_searchable=False),
            Property(name="journal", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="year", data_type=DataType.INT, index_filterable=True, index_searchable=False),
            Property(name="keywords", data_type=DataType.TEXT_ARRAY, index_filterable=True, index_searchable=False),
            Property(name="section", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="chunkIndex", data_type=DataType.INT, index_filterable=True, index_searchable=False),
            Property(name="content", data_type=DataType.TEXT, index_filterable=False, index_searchable=True),
            Property(name="offsetStart", data_type=DataType.INT, index_filterable=False, index_searchable=False),
            Property(name="offsetEnd", data_type=DataType.INT, index_filterable=False, index_searchable=False),
            Property(name="textVersion", data_type=DataType.TEXT, index_filterable=True, index_searchable=False),
            Property(name="sourceUrl", data_type=DataType.TEXT, index_filterable=False, index_searchable=False),
            Property(name="createdAt", data_type=DataType.DATE, index_filterable=True, index_searchable=False),
        ]
    )
    logger.info("collection_created", collection_name=collection_name)


def delete_sample_collection(client, collection_name: str) -> bool:
    """샘플 임베딩 컬렉션 삭제"""
    if client.collections.exists(collection_name):
        client.collections.delete(collection_name)
        logger.info("collection_deleted", collection_name=collection_name)
        return True
    return False


def get_embedded_paper_ids(client, collection_name: str) -> set[str]:
    """컬렉션에서 이미 임베딩된 paperId 목록 조회 (Resume용)

    Args:
        client: Weaviate 클라이언트
        collection_name: 컬렉션 이름

    Returns:
        이미 처리된 paperId set
    """
    if not client.collections.exists(collection_name):
        return set()

    try:
        collection = client.collections.get(collection_name)

        # paperId로 그룹화하여 유니크한 값만 조회
        embedded_ids = set()

        # aggregate로 모든 paperId 조회
        for item in collection.iterator(include_vector=False, return_properties=["paperId"]):
            if item.properties.get("paperId"):
                embedded_ids.add(item.properties["paperId"])

        logger.info(
            "embedded_paper_ids_retrieved",
            collection_name=collection_name,
            count=len(embedded_ids),
        )
        return embedded_ids

    except Exception as e:
        logger.warning(
            "embedded_paper_ids_retrieval_failed",
            collection_name=collection_name,
            error=str(e),
        )
        return set()


# ============================================================
# 데이터베이스 함수
# ============================================================


def get_sample_embedding(conn: psycopg.Connection, embedding_id: str) -> Optional[dict]:
    """샘플 임베딩 레코드 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, query_id, chunker, embedder, pipeline_key,
                   collection_name, status, paper_count, chunk_count,
                   error_message, created_at, started_at, completed_at
            FROM sample_embeddings
            WHERE id = %s
            """,
            (embedding_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        return {
            "id": str(row[0]),
            "query_id": str(row[1]),
            "chunker": row[2],
            "embedder": row[3],
            "pipeline_key": row[4],
            "collection_name": row[5],
            "status": row[6],
            "paper_count": row[7],
            "chunk_count": row[8],
            "error_message": row[9],
            "created_at": row[10],
            "started_at": row[11],
            "completed_at": row[12],
        }


def update_sample_embedding_status(
    conn: psycopg.Connection,
    embedding_id: str,
    status: str,
    paper_count: int = 0,
    chunk_count: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """샘플 임베딩 상태 업데이트"""
    with conn.cursor() as cur:
        now = datetime.now(timezone.utc)

        if status == "processing":
            cur.execute(
                """
                UPDATE sample_embeddings SET
                    status = %s,
                    started_at = %s
                WHERE id = %s
                """,
                (status, now, embedding_id),
            )
        elif status in ("completed", "failed"):
            cur.execute(
                """
                UPDATE sample_embeddings SET
                    status = %s,
                    paper_count = %s,
                    chunk_count = %s,
                    error_message = %s,
                    completed_at = %s
                WHERE id = %s
                """,
                (status, paper_count, chunk_count, error_message, now, embedding_id),
            )
        else:
            cur.execute(
                """
                UPDATE sample_embeddings SET
                    status = %s
                WHERE id = %s
                """,
                (status, embedding_id),
            )

        conn.commit()


def update_sample_embedding_progress(
    conn: psycopg.Connection,
    embedding_id: str,
    paper_count: int,
    chunk_count: int,
) -> None:
    """샘플 임베딩 진행 상황 업데이트 (처리 중)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sample_embeddings SET
                paper_count = %s,
                chunk_count = %s
            WHERE id = %s
            """,
            (paper_count, chunk_count, embedding_id),
        )
        conn.commit()


def get_papers_for_sample_query(
    conn: psycopg.Connection,
    query_id: str,
    limit: Optional[int] = None,
) -> list[dict]:
    """샘플 쿼리로 수집된 논문 목록 조회"""
    with conn.cursor() as cur:
        sql = """
            SELECT DISTINCT p.id, p.paper_id, p.pmcid, p.pmid, p.doi,
                   p.title, p.journal, p.year, p.keywords,
                   p.canonical_prefix
            FROM papers p
            JOIN batch_articles ba ON ba.pmcid = p.pmcid
            JOIN batch_jobs bj ON bj.id = ba.job_id
            WHERE bj.query_id = %s
              AND p.canonical_prefix IS NOT NULL
            ORDER BY p.created_at
        """

        if limit:
            sql += f" LIMIT {limit}"

        cur.execute(sql, (query_id,))

        return [
            {
                "id": row[0],
                "paper_id": row[1],
                "pmcid": row[2],
                "pmid": row[3],
                "doi": row[4],
                "title": row[5],
                "journal": row[6],
                "year": row[7],
                "keywords": row[8] or [],
                "canonical_prefix": row[9],
            }
            for row in cur.fetchall()
        ]


def get_paper_sections(conn: psycopg.Connection, paper_uuid: str) -> list[dict]:
    """논문의 섹션 정보 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT section_name, section_title, offset_start, offset_end
            FROM paper_sections
            WHERE paper_id = %s
            ORDER BY section_order
            """,
            (paper_uuid,),
        )
        return [
            {
                "name": row[0],
                "title": row[1],
                "offset_start": row[2],
                "offset_end": row[3],
            }
            for row in cur.fetchall()
        ]


def get_paper_authors(conn: psycopg.Connection, paper_uuid: str) -> list[str]:
    """논문의 저자 목록 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT author_name
            FROM paper_authors
            WHERE paper_id = %s
            ORDER BY author_order
            """,
            (paper_uuid,),
        )
        return [row[0] for row in cur.fetchall()]


# ============================================================
# 청킹/임베딩 팩토리 (새 RAG 모듈 사용)
# ============================================================

# 이름 매핑 (레거시 이름 -> 새 레지스트리 이름)
CHUNKER_NAME_MAP = {
    # 레거시 이름
    "semantic": "semantic_section_700t",
    "fixed": "fixed_char_1000_200",
    "large": "semantic_section_700t",  # large는 semantic으로 매핑
    # 새 이름 (그대로 사용)
    "semantic_section_700t": "semantic_section_700t",
    "fixed_char_1000_200": "fixed_char_1000_200",
}

EMBEDDER_NAME_MAP = {
    # 레거시 이름
    "openai": "openai_3small",
    "openai-large": "openai_3large",
    # 새 이름 (그대로 사용)
    "openai_3small": "openai_3small",
    "openai_3large": "openai_3large",
}


def get_chunker(chunker_name: str):
    """청커 인스턴스 생성 (새 RAG 레지스트리 사용)

    Args:
        chunker_name: 청커 이름 (레거시 또는 새 이름 모두 지원)

    Returns:
        청커 인스턴스
    """
    # 이름 매핑 (레거시 지원)
    registry_name = CHUNKER_NAME_MAP.get(chunker_name, "semantic_section_700t")
    logger.debug("chunker_resolved", input_name=chunker_name, registry_name=registry_name)
    return rag_get_chunker(registry_name)


def get_embedding_client(embedder_name: str):
    """임베딩 클라이언트 생성 (새 RAG 레지스트리 사용)

    Args:
        embedder_name: 임베더 이름 (레거시 또는 새 이름 모두 지원)

    Returns:
        임베더 인스턴스
    """
    # 이름 매핑 (레거시 지원)
    registry_name = EMBEDDER_NAME_MAP.get(embedder_name, "openai_3small")
    logger.debug("embedder_resolved", input_name=embedder_name, registry_name=registry_name)
    return rag_get_embedder(registry_name)


# ============================================================
# 임베딩 처리
# ============================================================


def process_paper_for_sample(
    pool: ConnectionPool,
    s3_storage: S3Storage,
    weaviate_client,
    collection,
    chunker,  # ChunkerProtocol (새 RAG 모듈)
    embedding_client,  # EmbedderProtocol (새 RAG 모듈)
    paper: dict,
) -> dict:
    """단일 논문 처리 (청킹 + 임베딩 + 저장)

    Returns:
        {"success": bool, "chunk_count": int, "error": str|None}
    """
    import uuid

    paper_id = paper["paper_id"]
    paper_uuid = str(paper["id"])

    try:
        # 1. S3에서 fulltext 읽기
        fulltext = s3_storage.get_fulltext(paper["canonical_prefix"])
        if not fulltext:
            raise ValueError(f"Fulltext not found: {paper['canonical_prefix']}")

        # 2. 섹션 정보 조회
        with pool.connection() as conn:
            sections = get_paper_sections(conn, paper_uuid)
            authors = get_paper_authors(conn, paper_uuid)

        if not sections:
            raise ValueError(f"No sections found for paper: {paper_id}")

        # 3. 청킹 (새 RAG 모듈 API 사용)
        chunking_result = chunker.chunk(
            fulltext=fulltext,
            sections=sections,
            paper_id=paper_id,
            title=paper["title"],
            year=paper.get("year"),
        )

        if not chunking_result.chunks:
            raise ValueError(f"No chunks created for paper: {paper_id}")

        # 4. 메타데이터 구성
        pmcid = paper.get("pmcid", "")
        source_url = f"https://europepmc.org/article/PMC/{pmcid}" if pmcid else None

        paper_metadata = {
            "pmcid": pmcid,
            "pmid": paper.get("pmid"),
            "doi": paper.get("doi"),
            "title": paper["title"],
            "authors": authors,
            "journal": paper.get("journal"),
            "year": paper.get("year"),
            "keywords": paper.get("keywords", []),
            "sourceUrl": source_url,
        }

        # 5. 배치 임베딩 + Weaviate 저장 (새 RAG 모듈 API 사용)
        chunks = chunking_result.chunks
        uuids = []
        batch_size = 10

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_texts = [c.embedding_text for c in batch_chunks]  # embedding_input -> embedding_text
            batch_embeddings = embedding_client.embed_batch(batch_texts)  # embed_texts -> embed_batch

            for chunk, embedding in zip(batch_chunks, batch_embeddings):
                object_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))

                properties = {
                    "paperId": chunk.paper_id,
                    "chunkId": chunk.chunk_id,
                    "embeddingVersion": embedding_client.get_version_string(),
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

                collection.data.insert(
                    uuid=object_uuid,
                    properties=properties,
                    vector=embedding,
                )
                uuids.append(object_uuid)

        logger.info(
            "paper_sample_embedded",
            paper_id=paper_id,
            chunk_count=len(uuids),
        )

        return {
            "success": True,
            "chunk_count": len(uuids),
            "error": None,
        }

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "paper_sample_embedding_failed",
            paper_id=paper_id,
            error=error_msg,
        )
        return {
            "success": False,
            "chunk_count": 0,
            "error": error_msg,
        }


# ============================================================
# Celery 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def run_sample_embed(self, embedding_id: str) -> dict:
    """샘플 임베딩 태스크 (Celery)

    Args:
        embedding_id: sample_embeddings 테이블의 ID

    Returns:
        실행 결과 dict
    """
    logger.info(
        "sample_embed_task_started",
        embedding_id=embedding_id,
        task_id=self.request.id,
    )

    pool = get_db_pool()
    weaviate_client = None

    try:
        # 1. 샘플 임베딩 레코드 조회
        with pool.connection() as conn:
            embedding = get_sample_embedding(conn, embedding_id)

        if not embedding:
            raise ValueError(f"Sample embedding not found: {embedding_id}")

        # Resume 지원: pending, failed, processing 상태 모두 허용
        if embedding["status"] not in ("pending", "failed", "processing"):
            raise ValueError(f"Invalid status for embedding: {embedding['status']}")

        is_resume = embedding["status"] == "processing"

        # 2. 상태 업데이트 (processing) - 이미 processing이면 스킵
        if not is_resume:
            with pool.connection() as conn:
                update_sample_embedding_status(conn, embedding_id, "processing")

        # 3. 클라이언트 초기화
        weaviate_client = get_weaviate_client()
        chunker = get_chunker(embedding["chunker"])
        embedding_client = get_embedding_client(embedding["embedder"])
        s3_storage = S3Storage()

        # 4. 컬렉션 생성 (없으면)
        collection_name = embedding["collection_name"]
        create_sample_collection(weaviate_client, collection_name)
        collection = weaviate_client.collections.get(collection_name)

        # 5. 샘플 쿼리로 수집된 논문 조회
        with pool.connection() as conn:
            all_papers = get_papers_for_sample_query(conn, embedding["query_id"])

        if not all_papers:
            raise ValueError(f"No papers found for query: {embedding['query_id']}")

        # 6. Resume: 이미 처리된 논문 필터링
        embedded_paper_ids = get_embedded_paper_ids(weaviate_client, collection_name)
        papers = [p for p in all_papers if p["paper_id"] not in embedded_paper_ids]

        # 기존에 처리된 paper_count, chunk_count 가져오기 (resume인 경우)
        existing_paper_count = embedding["paper_count"] or 0
        existing_chunk_count = embedding["chunk_count"] or 0

        logger.info(
            "sample_embed_papers_found",
            embedding_id=embedding_id,
            total_papers=len(all_papers),
            already_embedded=len(embedded_paper_ids),
            remaining_papers=len(papers),
            is_resume=is_resume,
        )

        # 모든 논문이 이미 처리됨
        if not papers:
            logger.info(
                "sample_embed_all_papers_already_embedded",
                embedding_id=embedding_id,
                paper_count=len(all_papers),
            )
            with pool.connection() as conn:
                update_sample_embedding_status(
                    conn, embedding_id, "completed",
                    paper_count=existing_paper_count,
                    chunk_count=existing_chunk_count,
                )
            return {
                "embedding_id": embedding_id,
                "collection_name": collection_name,
                "total_papers": len(all_papers),
                "completed": existing_paper_count,
                "failed": 0,
                "total_chunks": existing_chunk_count,
                "status": "completed",
                "message": "All papers already embedded (resumed)",
            }

        # 6. 논문별 처리 (병렬)
        completed = 0
        failed = 0
        total_chunks = 0
        errors = []
        processed_count = 0
        progress_lock = Lock()

        def process_paper_wrapper(paper):
            """병렬 처리용 래퍼"""
            return process_paper_for_sample(
                pool, s3_storage, weaviate_client, collection,
                chunker, embedding_client, paper
            ), paper["paper_id"]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_paper_wrapper, paper): paper for paper in papers}

            for future in as_completed(futures):
                result, paper_id = future.result()

                with progress_lock:
                    processed_count += 1
                    if result["success"]:
                        completed += 1
                        total_chunks += result["chunk_count"]
                    else:
                        failed += 1
                        errors.append(f"{paper_id}: {result['error']}")

                    # 주기적으로 progress 업데이트 (DB에 저장) - 기존 count 누적
                    if processed_count % PROGRESS_UPDATE_INTERVAL == 0:
                        try:
                            with pool.connection() as conn:
                                update_sample_embedding_progress(
                                    conn, embedding_id,
                                    existing_paper_count + completed,
                                    existing_chunk_count + total_chunks,
                                )
                        except Exception as e:
                            logger.warning("progress_update_failed", error=str(e))

                        logger.info(
                            "sample_embed_progress",
                            embedding_id=embedding_id,
                            processed=processed_count,
                            total=len(papers),
                            completed=completed,
                            failed=failed,
                            total_chunks=total_chunks,
                            cumulative_papers=existing_paper_count + completed,
                            cumulative_chunks=existing_chunk_count + total_chunks,
                        )

        # 7. 최종 count 계산 (기존 + 신규)
        final_paper_count = existing_paper_count + completed
        final_chunk_count = existing_chunk_count + total_chunks

        # 8. 상태 업데이트 (completed or failed)
        final_status = "completed" if failed == 0 else "completed"  # partial도 completed로 처리
        error_message = "\n".join(errors[:10]) if errors else None  # 최대 10개 에러만

        with pool.connection() as conn:
            update_sample_embedding_status(
                conn, embedding_id, final_status,
                paper_count=final_paper_count,
                chunk_count=final_chunk_count,
                error_message=error_message,
            )

        result = {
            "embedding_id": embedding_id,
            "collection_name": collection_name,
            "total_papers": len(all_papers),
            "newly_processed": len(papers),
            "completed": completed,
            "failed": failed,
            "total_chunks": final_chunk_count,
            "status": final_status,
            "is_resume": is_resume,
        }

        logger.info("sample_embed_completed", **result)
        return result

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "sample_embed_task_failed",
            embedding_id=embedding_id,
            error=error_msg,
        )

        # 상태 업데이트 (failed)
        try:
            with pool.connection() as conn:
                update_sample_embedding_status(
                    conn, embedding_id, "failed",
                    error_message=error_msg,
                )
        except Exception:
            pass

        raise

    finally:
        if weaviate_client:
            weaviate_client.close()


@app.task(bind=True, queue="embed")
def delete_sample_embed(self, embedding_id: str) -> dict:
    """샘플 임베딩 삭제 태스크 (Celery)

    Weaviate 컬렉션과 DB 레코드를 삭제합니다.

    Args:
        embedding_id: sample_embeddings 테이블의 ID

    Returns:
        삭제 결과 dict
    """
    logger.info(
        "sample_embed_delete_started",
        embedding_id=embedding_id,
        task_id=self.request.id,
    )

    pool = get_db_pool()
    weaviate_client = None

    try:
        # 1. 샘플 임베딩 레코드 조회
        with pool.connection() as conn:
            embedding = get_sample_embedding(conn, embedding_id)

        if not embedding:
            return {"success": False, "error": "Embedding not found"}

        # 2. Weaviate 컬렉션 삭제
        weaviate_client = get_weaviate_client()
        collection_deleted = delete_sample_collection(
            weaviate_client, embedding["collection_name"]
        )

        # 3. DB 레코드 삭제
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sample_embeddings WHERE id = %s",
                    (embedding_id,),
                )
                conn.commit()

        result = {
            "success": True,
            "embedding_id": embedding_id,
            "collection_name": embedding["collection_name"],
            "collection_deleted": collection_deleted,
        }

        logger.info("sample_embed_deleted", **result)
        return result

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "sample_embed_delete_failed",
            embedding_id=embedding_id,
            error=error_msg,
        )
        raise

    finally:
        if weaviate_client:
            weaviate_client.close()


# ============================================================
# V2: JobStateManager 기반 새 아키텍처
# ============================================================


@app.task(bind=True, queue="embed")
def run_sample_embed_v2(self, embedding_id: str) -> dict:
    """샘플 임베딩 태스크 V2 (JobStateManager 사용)

    Job Dispatcher에서 호출됨. Redis 기반 상태 관리 및 heartbeat 지원.

    Args:
        embedding_id: sample_embeddings 테이블의 ID

    Returns:
        실행 결과 dict
    """
    import socket
    from ..job_manager import get_job_manager, JobType, JobStatus

    manager = get_job_manager()
    worker_id = f"celery@{socket.gethostname()}"
    pool = get_db_pool()
    weaviate_client = None

    logger.info(
        "sample_embed_v2_started",
        embedding_id=embedding_id,
        task_id=self.request.id,
        worker_id=worker_id,
    )

    try:
        # 1. 락 확인 (이미 dispatcher가 획득했어야 함)
        state = manager.get_job_state(embedding_id, JobType.EMBED)
        if not state:
            # Redis에 없으면 DB에서 동기화
            with pool.connection() as conn:
                embedding = get_sample_embedding(conn, embedding_id)
            if not embedding:
                raise ValueError(f"Sample embedding not found: {embedding_id}")

            manager.sync_from_db(
                embedding_id,
                JobType.EMBED,
                embedding["status"],
                {
                    "paper_count": embedding["paper_count"] or 0,
                    "chunk_count": embedding["chunk_count"] or 0,
                    "error_message": embedding.get("error_message"),
                }
            )

        # 2. DB에서 임베딩 정보 조회
        with pool.connection() as conn:
            embedding = get_sample_embedding(conn, embedding_id)

        if not embedding:
            raise ValueError(f"Sample embedding not found: {embedding_id}")

        # 3. Weaviate, Chunker, Embedder 초기화
        weaviate_client = get_weaviate_client()
        chunker = get_chunker(embedding["chunker"])
        embedding_client = get_embedding_client(embedding["embedder"])
        s3_storage = S3Storage()

        collection_name = embedding["collection_name"]
        create_sample_collection(weaviate_client, collection_name)
        collection = weaviate_client.collections.get(collection_name)

        # 4. 논문 조회 + Resume 로직
        with pool.connection() as conn:
            all_papers = get_papers_for_sample_query(conn, embedding["query_id"])

        if not all_papers:
            raise ValueError(f"No papers found for query: {embedding['query_id']}")

        # 이미 처리된 논문 필터링
        embedded_paper_ids = get_embedded_paper_ids(weaviate_client, collection_name)
        papers = [p for p in all_papers if p["paper_id"] not in embedded_paper_ids]

        existing_paper_count = embedding["paper_count"] or 0
        existing_chunk_count = embedding["chunk_count"] or 0

        # 5. Job 시작 (Redis 상태 업데이트)
        manager.start_job(
            embedding_id,
            JobType.EMBED,
            worker_id,
            total=len(papers),
        )

        # DB 상태도 processing으로
        with pool.connection() as conn:
            update_sample_embedding_status(conn, embedding_id, "processing")

        logger.info(
            "sample_embed_v2_papers_found",
            embedding_id=embedding_id,
            total_papers=len(all_papers),
            already_embedded=len(embedded_paper_ids),
            remaining_papers=len(papers),
        )

        # 모든 논문이 이미 처리됨
        if not papers:
            manager.complete_job(
                embedding_id,
                JobType.EMBED,
                worker_id,
                {"paper_count": existing_paper_count, "chunk_count": existing_chunk_count},
            )
            with pool.connection() as conn:
                update_sample_embedding_status(
                    conn, embedding_id, "completed",
                    paper_count=existing_paper_count,
                    chunk_count=existing_chunk_count,
                )
            return {
                "embedding_id": embedding_id,
                "status": "completed",
                "message": "All papers already embedded",
            }

        # 6. 병렬 처리
        completed = 0
        failed = 0
        total_chunks = 0
        errors = []
        processed_count = 0
        progress_lock = Lock()
        heartbeat_counter = 0

        def process_paper_wrapper(paper):
            return process_paper_for_sample(
                pool, s3_storage, weaviate_client, collection,
                chunker, embedding_client, paper
            ), paper["paper_id"]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_paper_wrapper, paper): paper for paper in papers}

            for future in as_completed(futures):
                result, paper_id = future.result()

                with progress_lock:
                    processed_count += 1
                    heartbeat_counter += 1

                    if result["success"]:
                        completed += 1
                        total_chunks += result["chunk_count"]
                    else:
                        failed += 1
                        errors.append(f"{paper_id}: {result['error']}")

                    # 진행률 + Heartbeat 업데이트 (5개마다 또는 heartbeat 간격)
                    if processed_count % PROGRESS_UPDATE_INTERVAL == 0:
                        cumulative_papers = existing_paper_count + completed
                        cumulative_chunks = existing_chunk_count + total_chunks

                        # Redis 업데이트 (heartbeat 포함)
                        manager.update_progress(
                            embedding_id,
                            JobType.EMBED,
                            progress=completed,
                            total=len(papers),
                            extra={"chunk_count": cumulative_chunks},
                        )

                        # 락 연장
                        manager.extend_lock(embedding_id, JobType.EMBED, worker_id)

                        # DB 업데이트
                        try:
                            with pool.connection() as conn:
                                update_sample_embedding_progress(
                                    conn, embedding_id,
                                    cumulative_papers,
                                    cumulative_chunks,
                                )
                        except Exception as e:
                            logger.warning("progress_db_update_failed", error=str(e))

                        logger.info(
                            "sample_embed_v2_progress",
                            embedding_id=embedding_id,
                            processed=processed_count,
                            total=len(papers),
                            completed=completed,
                            failed=failed,
                        )

        # 7. 완료 처리
        final_paper_count = existing_paper_count + completed
        final_chunk_count = existing_chunk_count + total_chunks
        final_status = "completed"
        error_message = "\n".join(errors[:10]) if errors else None

        # Redis 완료
        manager.complete_job(
            embedding_id,
            JobType.EMBED,
            worker_id,
            {
                "paper_count": final_paper_count,
                "chunk_count": final_chunk_count,
            },
        )

        # DB 완료
        with pool.connection() as conn:
            update_sample_embedding_status(
                conn, embedding_id, final_status,
                paper_count=final_paper_count,
                chunk_count=final_chunk_count,
                error_message=error_message,
            )

        result = {
            "embedding_id": embedding_id,
            "collection_name": collection_name,
            "total_papers": len(all_papers),
            "newly_processed": len(papers),
            "completed": completed,
            "failed": failed,
            "total_chunks": final_chunk_count,
            "status": final_status,
        }

        logger.info("sample_embed_v2_completed", **result)
        return result

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "sample_embed_v2_failed",
            embedding_id=embedding_id,
            error=error_msg,
        )

        # Redis 실패 상태
        manager.fail_job(embedding_id, JobType.EMBED, worker_id, error_msg)

        # DB 실패 상태
        try:
            with pool.connection() as conn:
                update_sample_embedding_status(
                    conn, embedding_id, "failed",
                    error_message=error_msg,
                )
        except Exception:
            pass

        raise

    finally:
        if weaviate_client:
            weaviate_client.close()