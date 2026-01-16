"""임베딩 태스크 (청킹 + 벡터화)

- papers 테이블에서 수집된 논문 조회
- S3에서 fulltext.txt 읽기
- TextChunker로 청킹
- OpenAI 임베딩 생성
- Weaviate에 저장

흐름:
1. run_embed(query_id) → 해당 쿼리로 수집된 논문 일괄 임베딩
2. run_embed_paper(paper_id) → 단일 논문 임베딩

변경 이력:
- 2026-01-15: asyncio.gather 기반 비동기 처리로 변경 (ThreadPoolExecutor 대체)
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
import uuid as uuid_module

import psycopg
import structlog
from psycopg_pool import ConnectionPool

from ..celery_app import app
from ..config import settings
from ..storage import S3Storage
from ..chunker import TextChunker
from ..embedding import AsyncEmbeddingClient, EmbeddingClient, WeaviateClient
from ..job_manager import get_job_manager, JobType, JobStatus

logger = structlog.get_logger()

# 병렬 처리 설정 (OpenAI rate limit 고려)
# - OpenAI embedding: 3,000 RPM, 1,000,000 TPM
# - 논문당 ~30청크, 배치 10개씩 = ~3 requests/paper
# - asyncio는 더 많은 동시성 허용 (코루틴은 경량)
MAX_WORKERS = 5  # 동시 처리 논문 수 (ThreadPoolExecutor용, 하위 호환)
MAX_CONCURRENT = 10  # asyncio 동시 처리 수
PROGRESS_UPDATE_INTERVAL = 5  # N개 논문 처리 후 progress 업데이트


# ============================================================
# 팩토리 함수
# ============================================================


def get_chunker() -> TextChunker:
    """TextChunker 인스턴스 생성"""
    return TextChunker()


def get_embedding_client() -> EmbeddingClient:
    """EmbeddingClient 인스턴스 생성 (동기)"""
    return EmbeddingClient(
        api_key=settings.openai.api_key,
        model=settings.openai.embedding_model,
        dimensions=settings.openai.embedding_dimensions,
    )


def get_async_embedding_client() -> AsyncEmbeddingClient:
    """AsyncEmbeddingClient 인스턴스 생성 (비동기)"""
    return AsyncEmbeddingClient(
        api_key=settings.openai.api_key,
        model=settings.openai.embedding_model,
        dimensions=settings.openai.embedding_dimensions,
    )


def get_weaviate_client() -> WeaviateClient:
    """WeaviateClient 인스턴스 생성 (EmbeddingClient 포함)"""
    embedding_client = get_embedding_client()
    return WeaviateClient(
        host=settings.weaviate.host,
        port=settings.weaviate.port,
        embedding_client=embedding_client,
    )


# ============================================================
# Connection Pool (Celery 워커에서 재사용)
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
        logger.info("embed_db_pool_created", min_size=2, max_size=10)
    return _db_pool


# ============================================================
# 데이터베이스 함수
# ============================================================


def get_papers_for_embedding(
    conn: psycopg.Connection,
    query_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    status_filter: str = "pending",
) -> list[dict]:
    """임베딩할 논문 목록 조회

    Args:
        conn: DB 연결
        query_id: 특정 쿼리로 수집된 논문만 조회 (None이면 전체)
        limit: 최대 조회 수
        offset: 시작 위치
        status_filter: 임베딩 상태 필터 (pending, completed, failed)

    Returns:
        논문 정보 리스트
    """
    with conn.cursor() as cur:
        if query_id:
            # 특정 쿼리로 수집된 논문만
            cur.execute(
                """
                SELECT p.id, p.paper_id, p.pmcid, p.pmid, p.doi,
                       p.title, p.journal, p.year, p.keywords,
                       p.canonical_prefix, p.embedding_status
                FROM papers p
                JOIN batch_articles aj ON aj.pmcid = p.pmcid
                JOIN batch_jobs cj ON cj.id = aj.job_id
                WHERE cj.query_id = %s
                  AND (p.embedding_status = %s OR p.embedding_status IS NULL)
                  AND p.canonical_prefix IS NOT NULL
                ORDER BY p.created_at
                LIMIT %s OFFSET %s
                """,
                (query_id, status_filter if status_filter != "pending" else None, limit, offset),
            )
        else:
            # 전체 논문
            cur.execute(
                """
                SELECT id, paper_id, pmcid, pmid, doi,
                       title, journal, year, keywords,
                       canonical_prefix, embedding_status
                FROM papers
                WHERE (embedding_status = %s OR embedding_status IS NULL)
                  AND canonical_prefix IS NOT NULL
                ORDER BY created_at
                LIMIT %s OFFSET %s
                """,
                (status_filter if status_filter != "pending" else None, limit, offset),
            )

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
                "embedding_status": row[10],
            }
            for row in cur.fetchall()
        ]


def get_paper_by_id(conn: psycopg.Connection, paper_id: str) -> Optional[dict]:
    """논문 ID로 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, paper_id, pmcid, pmid, doi,
                   title, journal, year, keywords,
                   canonical_prefix, embedding_status
            FROM papers
            WHERE paper_id = %s
            """,
            (paper_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        return {
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
            "embedding_status": row[10],
        }


def get_paper_sections(conn: psycopg.Connection, paper_uuid: str) -> list[dict]:
    """논문의 섹션 정보 조회

    Args:
        conn: DB 연결
        paper_uuid: papers.id (UUID)
    """
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
    """논문의 저자 목록 조회

    Args:
        conn: DB 연결
        paper_uuid: papers.id (UUID)
    """
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


def update_embedding_status(
    conn: psycopg.Connection,
    paper_id: str,
    status: str,
    chunk_count: int = 0,
    error_msg: Optional[str] = None,
) -> None:
    """논문의 임베딩 상태 업데이트"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE papers SET
                embedding_status = %s,
                embedding_chunk_count = %s,
                embedding_error = %s,
                embedding_at = %s,
                updated_at = NOW()
            WHERE paper_id = %s
            """,
            (
                status,
                chunk_count,
                error_msg,
                datetime.now(timezone.utc) if status == "completed" else None,
                paper_id,
            ),
        )
        conn.commit()


def count_pending_papers(conn: psycopg.Connection, query_id: Optional[str] = None) -> int:
    """임베딩 대기 중인 논문 수 조회"""
    with conn.cursor() as cur:
        if query_id:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM papers p
                JOIN batch_articles aj ON aj.pmcid = p.pmcid
                JOIN batch_jobs cj ON cj.id = aj.job_id
                WHERE cj.query_id = %s
                  AND (p.embedding_status IS NULL OR p.embedding_status = 'pending')
                  AND p.canonical_prefix IS NOT NULL
                """,
                (query_id,),
            )
        else:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM papers
                WHERE (embedding_status IS NULL OR embedding_status = 'pending')
                  AND canonical_prefix IS NOT NULL
                """
            )
        return cur.fetchone()[0]


# ============================================================
# 임베딩 처리 함수
# ============================================================


def process_single_paper(
    pool: ConnectionPool,
    s3_storage: S3Storage,
    weaviate_client,
    chunker,
    paper: dict,
) -> dict:
    """단일 논문 청킹 및 임베딩

    Returns:
        {"success": bool, "chunk_count": int, "error": str|None}
    """
    paper_id = paper["paper_id"]  # VARCHAR (e.g., "pmc:PMC12345678")
    paper_uuid = str(paper["id"])  # UUID (for FK relations)

    try:
        # 1. S3에서 fulltext 읽기
        fulltext = s3_storage.get_fulltext(paper["canonical_prefix"])
        if not fulltext:
            raise ValueError(f"[TERMINAL:no_fulltext] Fulltext not found: {paper['canonical_prefix']}")

        # 2. 섹션 정보 조회 (paper_uuid 사용 - FK 관계)
        with pool.connection() as conn:
            sections = get_paper_sections(conn, paper_uuid)
            authors = get_paper_authors(conn, paper_uuid)
            update_embedding_status(conn, paper_id, "processing")

        if not sections:
            raise ValueError(f"[TERMINAL:no_sections] No sections found for paper: {paper_id}")

        # 3. 청킹
        chunking_result = chunker.chunk_paper(
            paper_id=paper_id,
            title=paper["title"],
            fulltext=fulltext,
            sections=sections,
            year=paper.get("year"),
        )

        if not chunking_result.chunks:
            raise ValueError(f"[TERMINAL:no_chunks] No chunks created for paper: {paper_id}")

        logger.info(
            "paper_chunked",
            paper_id=paper_id,
            chunk_count=len(chunking_result.chunks),
            avg_tokens=chunking_result.avg_chunk_tokens,
        )

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

        # 5. Weaviate에 저장 (배치 임베딩 포함)
        uuids = weaviate_client.insert_chunking_result(
            result=chunking_result,
            paper_metadata=paper_metadata,
            batch_size=10,
        )

        # 6. 상태 업데이트
        with pool.connection() as conn:
            update_embedding_status(
                conn, paper_id, "completed",
                chunk_count=len(uuids),
            )

        logger.info(
            "paper_embedded",
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
            "paper_embedding_failed",
            paper_id=paper_id,
            error=error_msg,
        )

        with pool.connection() as conn:
            update_embedding_status(
                conn, paper_id, "failed",
                error_msg=error_msg,
            )

        return {
            "success": False,
            "chunk_count": 0,
            "error": error_msg,
        }


def process_single_paper_v2(
    pool: ConnectionPool,
    s3_storage: S3Storage,
    collection,  # Weaviate collection 객체 (스레드 안전)
    embedding_client: EmbeddingClient,
    chunker,
    paper: dict,
) -> dict:
    """단일 논문 청킹 및 임베딩 (스레드 안전 버전)

    WeaviateClient 대신 collection과 embedding_client를 직접 받아
    ThreadPoolExecutor에서 안전하게 사용할 수 있습니다.

    Returns:
        {"success": bool, "chunk_count": int, "error": str|None}
    """
    paper_id = paper["paper_id"]
    paper_uuid = str(paper["id"])

    try:
        # 1. S3에서 fulltext 읽기
        fulltext = s3_storage.get_fulltext(paper["canonical_prefix"])
        if not fulltext:
            raise ValueError(f"[TERMINAL:no_fulltext] Fulltext not found: {paper['canonical_prefix']}")

        # 2. 섹션 정보 조회
        with pool.connection() as conn:
            sections = get_paper_sections(conn, paper_uuid)
            authors = get_paper_authors(conn, paper_uuid)
            update_embedding_status(conn, paper_id, "processing")

        if not sections:
            raise ValueError(f"[TERMINAL:no_sections] No sections found for paper: {paper_id}")

        # 3. 청킹
        chunking_result = chunker.chunk_paper(
            paper_id=paper_id,
            title=paper["title"],
            fulltext=fulltext,
            sections=sections,
            year=paper.get("year"),
        )

        if not chunking_result.chunks:
            raise ValueError(f"[TERMINAL:no_chunks] No chunks created for paper: {paper_id}")

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

        # 5. 배치 임베딩 + Weaviate 저장 (collection 직접 사용)
        chunks = chunking_result.chunks
        uuids = []
        batch_size = 10

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_texts = [c.embedding_input for c in batch_chunks]
            batch_embeddings = embedding_client.embed_texts(batch_texts)

            for chunk, embedding in zip(batch_chunks, batch_embeddings):
                object_uuid = str(
                    uuid_module.uuid5(uuid_module.NAMESPACE_DNS, chunk.chunk_id)
                )

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

        # 6. 상태 업데이트
        with pool.connection() as conn:
            update_embedding_status(
                conn,
                paper_id,
                "completed",
                chunk_count=len(uuids),
            )

        logger.info(
            "paper_embedded",
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
            "paper_embedding_failed",
            paper_id=paper_id,
            error=error_msg,
        )

        try:
            with pool.connection() as conn:
                update_embedding_status(
                    conn,
                    paper_id,
                    "failed",
                    error_msg=error_msg,
                )
        except Exception:
            pass  # 상태 업데이트 실패해도 계속 진행

        return {
            "success": False,
            "chunk_count": 0,
            "error": error_msg,
        }


async def process_single_paper_async(
    pool: ConnectionPool,
    s3_storage: S3Storage,
    collection,  # Weaviate collection 객체
    embedding_client: AsyncEmbeddingClient,
    chunker,
    paper: dict,
) -> dict:
    """단일 논문 청킹 및 임베딩 (비동기 버전)

    AsyncEmbeddingClient를 사용하여 asyncio.gather()와 함께
    병렬 처리할 수 있습니다.

    Returns:
        {"success": bool, "chunk_count": int, "error": str|None}
    """
    paper_id = paper["paper_id"]
    paper_uuid = str(paper["id"])

    try:
        # 1. S3에서 fulltext 읽기 (동기 - to_thread로 래핑)
        fulltext = await asyncio.to_thread(s3_storage.get_fulltext, paper["canonical_prefix"])
        if not fulltext:
            raise ValueError(f"[TERMINAL:no_fulltext] Fulltext not found: {paper['canonical_prefix']}")

        # 2. 섹션 정보 조회 (동기 DB - to_thread로 래핑)
        def _get_paper_info():
            with pool.connection() as conn:
                sections = get_paper_sections(conn, paper_uuid)
                authors = get_paper_authors(conn, paper_uuid)
                update_embedding_status(conn, paper_id, "processing")
            return sections, authors

        sections, authors = await asyncio.to_thread(_get_paper_info)

        if not sections:
            raise ValueError(f"[TERMINAL:no_sections] No sections found for paper: {paper_id}")

        # 3. 청킹 (CPU 바운드 - to_thread로 래핑)
        chunking_result = await asyncio.to_thread(
            chunker.chunk_paper,
            paper_id=paper_id,
            title=paper["title"],
            fulltext=fulltext,
            sections=sections,
            year=paper.get("year"),
        )

        if not chunking_result.chunks:
            raise ValueError(f"[TERMINAL:no_chunks] No chunks created for paper: {paper_id}")

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

        # 5. 배치 임베딩 + Weaviate 저장 (비동기!)
        chunks = chunking_result.chunks
        uuids = []
        batch_size = 10

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_texts = [c.embedding_input for c in batch_chunks]

            # 비동기 임베딩!
            batch_embeddings = await embedding_client.embed_texts(batch_texts)

            # Weaviate 저장 (동기 - to_thread로 래핑)
            def _insert_batch(batch_chunks, batch_embeddings):
                inserted = []
                for chunk, embedding in zip(batch_chunks, batch_embeddings):
                    object_uuid = str(
                        uuid_module.uuid5(uuid_module.NAMESPACE_DNS, chunk.chunk_id)
                    )

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
                    inserted.append(object_uuid)
                return inserted

            batch_uuids = await asyncio.to_thread(_insert_batch, batch_chunks, batch_embeddings)
            uuids.extend(batch_uuids)

        # 6. 상태 업데이트 (동기 DB - to_thread로 래핑)
        def _update_status():
            with pool.connection() as conn:
                update_embedding_status(
                    conn,
                    paper_id,
                    "completed",
                    chunk_count=len(uuids),
                )

        await asyncio.to_thread(_update_status)

        logger.info(
            "paper_embedded_async",
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
            "paper_embedding_failed_async",
            paper_id=paper_id,
            error=error_msg,
        )

        try:
            def _update_failed():
                with pool.connection() as conn:
                    update_embedding_status(
                        conn,
                        paper_id,
                        "failed",
                        error_msg=error_msg,
                    )
            await asyncio.to_thread(_update_failed)
        except Exception:
            pass  # 상태 업데이트 실패해도 계속 진행

        return {
            "success": False,
            "chunk_count": 0,
            "error": error_msg,
        }


def run_embed_async(
    query_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """임베딩 실행 (병렬 처리)

    Args:
        query_id: 특정 쿼리로 수집된 논문만 처리 (None이면 전체)
        limit: 처리할 최대 논문 수 (None이면 전체)

    Returns:
        실행 결과
    """
    pool = get_db_pool()
    s3_storage = S3Storage()

    # Weaviate/Chunker 초기화
    weaviate_client = get_weaviate_client()
    chunker = get_chunker()

    try:
        # 1. 처리할 논문 조회
        with pool.connection() as conn:
            total_pending = count_pending_papers(conn, query_id)
            papers = get_papers_for_embedding(
                conn, query_id,
                limit=limit or total_pending,
                status_filter="pending",
            )

        if not papers:
            logger.info("no_papers_to_embed", query_id=query_id)
            return {
                "query_id": query_id,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "status": "no_papers",
            }

        logger.info(
            "embed_started",
            query_id=query_id,
            total_papers=len(papers),
            max_workers=MAX_WORKERS,
        )

        # 2. 병렬 처리 준비
        collection = weaviate_client.collection
        embedding_client = weaviate_client.embedding_client

        completed = 0
        failed = 0
        total_chunks = 0
        processed_count = 0
        progress_lock = Lock()

        def process_paper_wrapper(paper):
            """병렬 처리용 래퍼"""
            return process_single_paper_v2(
                pool, s3_storage, collection,
                embedding_client, chunker, paper
            ), paper["paper_id"]

        # 3. ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_paper_wrapper, paper): paper
                for paper in papers
            }

            for future in as_completed(futures):
                result, paper_id = future.result()

                with progress_lock:
                    processed_count += 1
                    if result["success"]:
                        completed += 1
                        total_chunks += result["chunk_count"]
                    else:
                        failed += 1

                    # 주기적으로 progress 로그 출력
                    if processed_count % PROGRESS_UPDATE_INTERVAL == 0:
                        logger.info(
                            "embed_progress",
                            processed=processed_count,
                            total=len(papers),
                            completed=completed,
                            failed=failed,
                        )

        # 4. 결과 반환
        result = {
            "query_id": query_id,
            "total": len(papers),
            "completed": completed,
            "failed": failed,
            "total_chunks": total_chunks,
            "status": "completed" if failed == 0 else "partial",
        }

        logger.info("embed_completed", **result)
        return result

    finally:
        weaviate_client.close()


async def run_embed_coroutine(
    query_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """비동기 임베딩 실행 (asyncio.gather 기반)

    ThreadPoolExecutor 대신 asyncio.gather()와 세마포어를 사용하여
    I/O 바운드 작업의 병렬성을 극대화합니다.

    Args:
        query_id: 특정 쿼리로 수집된 논문만 처리 (None이면 전체)
        limit: 처리할 최대 논문 수 (None이면 전체)

    Returns:
        실행 결과
    """
    pool = get_db_pool()
    s3_storage = S3Storage()

    # 비동기 임베딩 클라이언트 + Weaviate
    async_embedding_client = get_async_embedding_client()
    weaviate_client = get_weaviate_client()
    chunker = get_chunker()

    try:
        # 1. 처리할 논문 조회 (동기 DB - to_thread)
        def _get_papers():
            with pool.connection() as conn:
                total_pending = count_pending_papers(conn, query_id)
                return get_papers_for_embedding(
                    conn, query_id,
                    limit=limit or total_pending,
                    status_filter="pending",
                )

        papers = await asyncio.to_thread(_get_papers)

        if not papers:
            logger.info("no_papers_to_embed_async", query_id=query_id)
            return {
                "query_id": query_id,
                "total": 0,
                "completed": 0,
                "failed": 0,
                "status": "no_papers",
            }

        logger.info(
            "embed_started_async",
            query_id=query_id,
            total_papers=len(papers),
            max_concurrent=MAX_CONCURRENT,
        )

        # 2. 세마포어로 동시성 제어
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        collection = weaviate_client.collection

        async def process_with_semaphore(paper: dict) -> dict:
            async with semaphore:
                return await process_single_paper_async(
                    pool=pool,
                    s3_storage=s3_storage,
                    collection=collection,
                    embedding_client=async_embedding_client,
                    chunker=chunker,
                    paper=paper,
                )

        # 3. asyncio.gather로 병렬 처리
        tasks = [process_with_semaphore(paper) for paper in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. 결과 집계
        completed = 0
        failed = 0
        total_chunks = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
                logger.error(
                    "paper_embed_exception",
                    paper_id=papers[i]["paper_id"],
                    error=str(result)[:200],
                )
            elif result.get("success"):
                completed += 1
                total_chunks += result.get("chunk_count", 0)
            else:
                failed += 1

        # 5. 결과 반환
        final_result = {
            "query_id": query_id,
            "total": len(papers),
            "completed": completed,
            "failed": failed,
            "total_chunks": total_chunks,
            "status": "completed" if failed == 0 else "partial",
        }

        logger.info("embed_completed_async", **final_result)
        return final_result

    finally:
        weaviate_client.close()
        await async_embedding_client.close()


# ============================================================
# Celery 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def run_embed(
    self,
    query_id: Optional[str] = None,
    limit: Optional[int] = None,
    use_async: bool = True,
) -> dict:
    """임베딩 태스크 (Celery)

    수집된 논문을 청킹하고 임베딩하여 Weaviate에 저장합니다.

    Args:
        query_id: 특정 쿼리로 수집된 논문만 처리 (None이면 전체)
        limit: 처리할 최대 논문 수 (None이면 전체)
        use_async: True면 asyncio.gather 사용 (기본), False면 ThreadPoolExecutor

    Returns:
        실행 결과 dict
    """
    logger.info(
        "embed_task_started",
        query_id=query_id,
        limit=limit,
        task_id=self.request.id,
        use_async=use_async,
    )

    try:
        if use_async:
            # 비동기 버전 (asyncio.gather 기반) - 권장
            result = asyncio.run(run_embed_coroutine(query_id, limit))
        else:
            # 동기 버전 (ThreadPoolExecutor 기반) - 하위 호환
            result = run_embed_async(query_id, limit)
        return result

    except Exception as e:
        logger.error(
            "embed_task_failed",
            query_id=query_id,
            error=str(e),
        )
        raise


@app.task(bind=True, queue="embed")
def run_embed_paper(self, paper_id: str) -> dict:
    """단일 논문 임베딩 태스크 (Celery)

    Args:
        paper_id: 논문 ID (예: pmc:PMC12345678)

    Returns:
        실행 결과 dict
    """
    logger.info(
        "embed_paper_task_started",
        paper_id=paper_id,
        task_id=self.request.id,
    )

    pool = get_db_pool()
    s3_storage = S3Storage()
    weaviate_client = get_weaviate_client()
    chunker = get_chunker()

    try:
        # 논문 조회
        with pool.connection() as conn:
            paper = get_paper_by_id(conn, paper_id)

        if not paper:
            raise ValueError(f"Paper not found: {paper_id}")

        if not paper.get("canonical_prefix"):
            raise ValueError(f"Paper has no fulltext: {paper_id}")

        # 처리
        result = process_single_paper(
            pool, s3_storage, weaviate_client, chunker, paper
        )

        return {
            "paper_id": paper_id,
            **result,
        }

    except Exception as e:
        logger.error(
            "embed_paper_task_failed",
            paper_id=paper_id,
            error=str(e),
        )
        raise

    finally:
        weaviate_client.close()


@app.task(bind=True, queue="embed")
def run_reembed(
    self,
    query_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """재임베딩 태스크 (실패한 논문 재처리)

    Args:
        query_id: 특정 쿼리로 수집된 논문만 처리
        limit: 처리할 최대 논문 수

    Returns:
        실행 결과 dict
    """
    logger.info(
        "reembed_task_started",
        query_id=query_id,
        limit=limit,
        task_id=self.request.id,
    )

    pool = get_db_pool()

    # 실패한 논문 상태를 pending으로 변경
    # 단, TERMINAL 에러(재시도 의미 없음)는 제외
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if query_id:
                cur.execute(
                    """
                    UPDATE papers SET
                        embedding_status = 'pending',
                        embedding_error = NULL
                    WHERE paper_id IN (
                        SELECT p.paper_id
                        FROM papers p
                        JOIN article_jobs aj ON aj.pmcid = p.pmcid
                        JOIN collection_jobs cj ON cj.id = aj.batch_job_id
                        WHERE cj.query_id = %s
                          AND p.embedding_status = 'failed'
                          AND (p.embedding_error IS NULL OR p.embedding_error NOT LIKE '[TERMINAL:%%]%%')
                    )
                    """,
                    (query_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE papers SET
                        embedding_status = 'pending',
                        embedding_error = NULL
                    WHERE embedding_status = 'failed'
                      AND (embedding_error IS NULL OR embedding_error NOT LIKE '[TERMINAL:%%]%%')
                    """
                )
            reset_count = cur.rowcount
            conn.commit()

        # TERMINAL 에러로 제외된 논문 수 조회
        with conn.cursor() as cur:
            if query_id:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM papers p
                    JOIN article_jobs aj ON aj.pmcid = p.pmcid
                    JOIN collection_jobs cj ON cj.id = aj.batch_job_id
                    WHERE cj.query_id = %s
                      AND p.embedding_status = 'failed'
                      AND p.embedding_error LIKE '[TERMINAL:%%]%%'
                    """,
                    (query_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM papers
                    WHERE embedding_status = 'failed'
                      AND embedding_error LIKE '[TERMINAL:%%]%%'
                    """
                )
            terminal_count = cur.fetchone()[0]

    logger.info(
        "reembed_reset",
        reset_count=reset_count,
        terminal_skipped=terminal_count,
    )

    # 임베딩 실행
    return run_embed_async(query_id, limit)


# ============================================================
# Job Manager V2 기반 태스크
# ============================================================


def get_papers_by_uuids(conn: psycopg.Connection, paper_uuids: list[str]) -> list[dict]:
    """UUID 목록으로 논문 조회

    Args:
        conn: DB 연결
        paper_uuids: papers.id (UUID) 목록

    Returns:
        논문 정보 리스트
    """
    if not paper_uuids:
        return []

    with conn.cursor() as cur:
        # UUID 목록을 배열로 변환하여 쿼리
        cur.execute(
            """
            SELECT id, paper_id, pmcid, pmid, doi,
                   title, journal, year, keywords,
                   canonical_prefix, embedding_status
            FROM papers
            WHERE id = ANY(%s)
              AND canonical_prefix IS NOT NULL
            ORDER BY created_at
            """,
            (paper_uuids,),
        )

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
                "embedding_status": row[10],
            }
            for row in cur.fetchall()
        ]


def get_worker_id() -> str:
    """현재 워커 식별자"""
    import socket
    return f"celery@{socket.gethostname()}"


@app.task(bind=True, queue="embed")
def run_paper_embed_v2(self, batch_id: str) -> dict:
    """Papers 임베딩 배치 태스크 (Job Manager V2)

    Admin Backend에서 생성된 배치 작업을 처리합니다.
    Redis에서 paper_ids를 가져와 순차적으로 처리하며,
    진행률을 실시간으로 업데이트합니다.

    Args:
        batch_id: 배치 작업 ID (예: paper_batch_20260109_143000)

    Returns:
        실행 결과 dict
    """
    manager = get_job_manager()
    worker_id = get_worker_id()

    logger.info(
        "paper_embed_v2_started",
        batch_id=batch_id,
        worker_id=worker_id,
        task_id=self.request.id,
    )

    # 1. 작업 상태 조회
    state = manager.get_job_state(batch_id, JobType.PAPER_EMBED)
    if not state:
        logger.error("paper_embed_v2_job_not_found", batch_id=batch_id)
        return {"error": "Job not found", "batch_id": batch_id}

    # 2. paper_ids 파싱 (metadata에 저장됨)
    import json
    paper_ids_json = state.get("paper_ids", "[]")
    try:
        paper_uuids = json.loads(paper_ids_json)
    except json.JSONDecodeError:
        logger.error("paper_embed_v2_invalid_paper_ids", batch_id=batch_id)
        manager.fail_job(batch_id, JobType.PAPER_EMBED, worker_id, "Invalid paper_ids")
        return {"error": "Invalid paper_ids", "batch_id": batch_id}

    if not paper_uuids:
        logger.warning("paper_embed_v2_no_papers", batch_id=batch_id)
        manager.complete_job(batch_id, JobType.PAPER_EMBED, worker_id, {"message": "No papers"})
        return {"batch_id": batch_id, "total": 0, "completed": 0, "failed": 0}

    # 3. 작업 시작
    manager.start_job(batch_id, JobType.PAPER_EMBED, worker_id, total=len(paper_uuids))

    # 4. 논문 조회
    pool = get_db_pool()
    s3_storage = S3Storage()
    weaviate_client = get_weaviate_client()
    chunker = get_chunker()

    try:
        with pool.connection() as conn:
            papers = get_papers_by_uuids(conn, paper_uuids)

        if not papers:
            logger.warning("paper_embed_v2_papers_not_found", batch_id=batch_id)
            manager.complete_job(batch_id, JobType.PAPER_EMBED, worker_id, {"message": "Papers not found"})
            return {"batch_id": batch_id, "total": 0, "completed": 0, "failed": 0}

        # 5. 병렬 처리 준비
        collection = weaviate_client.collection
        embedding_client = weaviate_client.embedding_client

        completed = 0
        failed = 0
        total_chunks = 0
        processed_count = 0
        progress_lock = Lock()
        is_cancelled = False

        logger.info(
            "paper_embed_v2_parallel_start",
            batch_id=batch_id,
            total_papers=len(papers),
            max_workers=MAX_WORKERS,
        )

        def process_paper_wrapper(paper):
            """병렬 처리용 래퍼"""
            return process_single_paper_v2(
                pool, s3_storage, collection,
                embedding_client, chunker, paper
            ), paper["paper_id"]

        # 6. ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_paper_wrapper, paper): paper
                for paper in papers
            }

            for future in as_completed(futures):
                # 작업 취소 확인 (매 완료마다)
                current_state = manager.get_job_state(batch_id, JobType.PAPER_EMBED)
                if current_state and current_state.get("status") == JobStatus.CANCELLED:
                    is_cancelled = True
                    logger.info(
                        "paper_embed_v2_cancelled",
                        batch_id=batch_id,
                        processed=processed_count,
                    )
                    # 남은 작업 취소
                    for f in futures:
                        f.cancel()
                    break

                result, paper_id = future.result()

                with progress_lock:
                    processed_count += 1
                    if result["success"]:
                        completed += 1
                        total_chunks += result["chunk_count"]
                    else:
                        failed += 1

                    # 진행률 업데이트 (5건마다 또는 마지막)
                    if processed_count % PROGRESS_UPDATE_INTERVAL == 0 or processed_count == len(papers):
                        manager.update_progress(
                            batch_id, JobType.PAPER_EMBED, processed_count, len(papers),
                            extra={"chunk_count": total_chunks},
                        )

                    # 로그 출력 (10건마다)
                    if processed_count % 10 == 0:
                        logger.info(
                            "paper_embed_v2_progress",
                            batch_id=batch_id,
                            processed=processed_count,
                            total=len(papers),
                            completed=completed,
                            failed=failed,
                        )

        # 7. 완료 처리
        result = {
            "batch_id": batch_id,
            "total": len(papers),
            "completed": completed,
            "failed": failed,
            "total_chunks": total_chunks,
        }

        if failed == 0:
            manager.complete_job(batch_id, JobType.PAPER_EMBED, worker_id, result)
            logger.info("paper_embed_v2_completed", **result)
        else:
            # 일부 실패해도 작업 자체는 완료로 처리
            manager.complete_job(batch_id, JobType.PAPER_EMBED, worker_id, result)
            logger.warning("paper_embed_v2_partial", **result)

        return result

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "paper_embed_v2_failed",
            batch_id=batch_id,
            error=error_msg,
        )
        manager.fail_job(batch_id, JobType.PAPER_EMBED, worker_id, error_msg)
        return {"error": error_msg, "batch_id": batch_id}

    finally:
        weaviate_client.close()
