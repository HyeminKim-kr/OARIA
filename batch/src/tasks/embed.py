"""임베딩 태스크 (청킹 + 벡터화)

- papers 테이블에서 수집된 논문 조회
- S3에서 fulltext.txt 읽기
- TextChunker로 청킹
- OpenAI 임베딩 생성
- Weaviate에 저장

흐름:
1. run_embed(query_id) → 해당 쿼리로 수집된 논문 일괄 임베딩
2. run_embed_paper(paper_id) → 단일 논문 임베딩
"""

from datetime import datetime, timezone
from typing import Optional

import psycopg
import structlog
from psycopg_pool import ConnectionPool

from ..celery_app import app
from ..config import settings
from ..storage import S3Storage
from ..chunker import TextChunker
from ..embedding import EmbeddingClient, WeaviateClient

logger = structlog.get_logger()


# ============================================================
# 팩토리 함수
# ============================================================


def get_chunker() -> TextChunker:
    """TextChunker 인스턴스 생성"""
    return TextChunker()


def get_embedding_client() -> EmbeddingClient:
    """EmbeddingClient 인스턴스 생성"""
    return EmbeddingClient(
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
            raise ValueError(f"Fulltext not found: {paper['canonical_prefix']}")

        # 2. 섹션 정보 조회 (paper_uuid 사용 - FK 관계)
        with pool.connection() as conn:
            sections = get_paper_sections(conn, paper_uuid)
            authors = get_paper_authors(conn, paper_uuid)
            update_embedding_status(conn, paper_id, "processing")

        if not sections:
            raise ValueError(f"No sections found for paper: {paper_id}")

        # 3. 청킹
        chunking_result = chunker.chunk_paper(
            paper_id=paper_id,
            title=paper["title"],
            fulltext=fulltext,
            sections=sections,
            year=paper.get("year"),
        )

        if not chunking_result.chunks:
            raise ValueError(f"No chunks created for paper: {paper_id}")

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


def run_embed_async(
    query_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """임베딩 실행 (동기)

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
        )

        # 2. 논문별 처리
        completed = 0
        failed = 0
        total_chunks = 0

        for i, paper in enumerate(papers, 1):
            result = process_single_paper(
                pool, s3_storage, weaviate_client, chunker, paper
            )

            if result["success"]:
                completed += 1
                total_chunks += result["chunk_count"]
            else:
                failed += 1

            if i % 10 == 0:
                logger.info(
                    "embed_progress",
                    processed=i,
                    total=len(papers),
                    completed=completed,
                    failed=failed,
                )

        # 3. 결과 반환
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


# ============================================================
# Celery 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def run_embed(
    self,
    query_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """임베딩 태스크 (Celery)

    수집된 논문을 청킹하고 임베딩하여 Weaviate에 저장합니다.

    Args:
        query_id: 특정 쿼리로 수집된 논문만 처리 (None이면 전체)
        limit: 처리할 최대 논문 수 (None이면 전체)

    Returns:
        실행 결과 dict
    """
    logger.info(
        "embed_task_started",
        query_id=query_id,
        limit=limit,
        task_id=self.request.id,
    )

    try:
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
                    """
                )
            reset_count = cur.rowcount
            conn.commit()

    logger.info("reembed_reset", reset_count=reset_count)

    # 임베딩 실행
    return run_embed_async(query_id, limit)
