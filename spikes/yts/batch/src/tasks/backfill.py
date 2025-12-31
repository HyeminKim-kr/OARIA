"""Backfill 태스크 (초기 적재)

OAR-21 설계 기반:
- search_queries에서 쿼리 조회
- Europe PMC 검색 → 전문 수집 → 파싱 → 저장
- collection_jobs 상태 관리
- article_jobs로 개별 논문 상태 관리
- 체크포인트 저장 (중단 재개)
"""

import asyncio
import json
from datetime import datetime, timedelta
from uuid import UUID

import psycopg
from psycopg_pool import ConnectionPool
import structlog

from ..celery_app import app
from ..collectors import EuropePMCClient
from ..config import settings
from ..parsers import XMLParser
from ..storage import DatabaseStorage, S3Storage
from ..storage.error_storage import ArticleError, ErrorStorage

# 체이닝: 수집 완료 후 임베딩 트리거
from .embed import run_embed

logger = structlog.get_logger()

# 모듈 레벨 Connection Pool (Celery 워커에서 재사용)
_db_pool: ConnectionPool | None = None


def get_db_pool() -> ConnectionPool:
    """Connection Pool 획득 (싱글톤)"""
    global _db_pool
    if _db_pool is None:
        _db_pool = ConnectionPool(
            conninfo=settings.db.dsn,
            min_size=2,
            max_size=40,  # max_concurrent(35) + 여유
            open=True,
        )
        logger.info("db_pool_created", min_size=2, max_size=40)
    return _db_pool


# ============================================================
# Article Jobs 관리 함수들
# ============================================================


def upsert_article_job(
    conn: psycopg.Connection,
    job_id: str,
    pmcid: str,
    pmid: str | None = None,
    doi: str | None = None,
) -> None:
    """article_jobs에 논문 등록 (중복 시 무시)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO article_jobs (batch_job_id, pmcid, pmid, doi, status)
            VALUES (%s, %s, %s, %s, 'pending')
            ON CONFLICT (batch_job_id, pmcid) DO NOTHING
            """,
            (job_id, pmcid, pmid, doi),
        )


def batch_upsert_article_jobs(
    conn: psycopg.Connection,
    job_id: str,
    articles: list[dict],
) -> int:
    """article_jobs에 배치로 논문 등록"""
    if not articles:
        return 0

    with conn.cursor() as cur:
        # psycopg3에서는 executemany 사용
        cur.executemany(
            """
            INSERT INTO article_jobs (batch_job_id, pmcid, pmid, doi, status)
            VALUES (%s, %s, %s, %s, 'pending')
            ON CONFLICT (batch_job_id, pmcid) DO NOTHING
            """,
            [(job_id, a["pmcid"], a.get("pmid"), a.get("doi")) for a in articles],
        )
        conn.commit()
        return len(articles)


def update_article_status(
    conn: psycopg.Connection,
    job_id: str,
    pmcid: str,
    status: str,
    error_code: str | None = None,
    error_msg: str | None = None,
) -> None:
    """article_jobs 상태 업데이트"""
    with conn.cursor() as cur:
        if status == "failed":
            # 실패 시 재시도 설정 (attempt_count < max_attempts이면)
            cur.execute(
                """
                UPDATE article_jobs SET
                    status = CASE
                        WHEN attempt_count + 1 < max_attempts THEN 'pending'
                        ELSE 'failed'
                    END,
                    attempt_count = attempt_count + 1,
                    next_run_at = CASE
                        WHEN attempt_count + 1 < max_attempts THEN NOW() + INTERVAL '5 minutes'
                        ELSE NULL
                    END,
                    last_error_code = %s,
                    last_error = %s,
                    updated_at = NOW()
                WHERE batch_job_id = %s AND pmcid = %s
                """,
                (error_code, error_msg, job_id, pmcid),
            )
        else:
            cur.execute(
                """
                UPDATE article_jobs SET
                    status = %s,
                    updated_at = NOW()
                WHERE batch_job_id = %s AND pmcid = %s
                """,
                (status, job_id, pmcid),
            )
        conn.commit()


def get_pending_articles(
    conn: psycopg.Connection,
    job_id: str,
    limit: int = 100,
) -> list[dict]:
    """처리할 pending 상태 논문 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pmcid, pmid, doi
            FROM article_jobs
            WHERE batch_job_id = %s
              AND status = 'pending'
              AND (next_run_at IS NULL OR next_run_at <= NOW())
            ORDER BY created_at
            LIMIT %s
            """,
            (job_id, limit),
        )
        return [
            {"pmcid": row[0], "pmid": row[1], "doi": row[2]}
            for row in cur.fetchall()
        ]


def get_article_job_stats(conn: psycopg.Connection, job_id: str) -> dict:
    """article_jobs 통계 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status IN ('downloading', 'parsing', 'saving')) as in_progress
            FROM article_jobs
            WHERE batch_job_id = %s
            """,
            (job_id,),
        )
        row = cur.fetchone()
        return {
            "total": row[0],
            "completed": row[1],
            "failed": row[2],
            "pending": row[3],
            "in_progress": row[4],
        }


def get_db_connection() -> psycopg.Connection:
    """DB 연결 (Pool 외부에서 단독 사용 시)"""
    return psycopg.connect(settings.db.dsn)


def get_pooled_connection():
    """Pool에서 연결 획득 (with 문과 함께 사용)"""
    return get_db_pool().connection()


def get_search_query(conn: psycopg.Connection, query_id: str) -> dict | None:
    """검색 쿼리 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, query, is_active, priority, max_results,
                   year_from, year_to, open_access_only, max_concurrent
            FROM search_queries
            WHERE id = %s AND is_active = true
            """,
            (query_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "query": row[2],
            "is_active": row[3],
            "priority": row[4],
            "max_results": row[5],
            "year_from": row[6],
            "year_to": row[7],
            "open_access_only": row[8],
            "max_concurrent": row[9] or 35,
        }


def create_job(
    conn: psycopg.Connection, query_id: str, query_text: str
) -> str:
    """collection_jobs 생성"""
    import socket
    worker_id = socket.gethostname()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO collection_jobs (
                job_type, query_id, priority, query, status,
                locked_at, locked_by, started_at, created_at
            ) VALUES (
                'backfill', %s, 10, %s, 'running',
                NOW(), %s, NOW(), NOW()
            )
            RETURNING id
            """,
            (query_id, query_text, worker_id),
        )
        job_id = cur.fetchone()[0]
        conn.commit()
        return str(job_id)


def update_job_progress(
    conn: psycopg.Connection,
    job_id: str,
    processed: int,
    success: int,
    failed: int,
    total: int | None = None,
    checkpoint: dict | None = None,
) -> None:
    """작업 진행률 업데이트 + heartbeat (locked_at)"""
    with conn.cursor() as cur:
        if checkpoint:
            cur.execute(
                """
                UPDATE collection_jobs SET
                    processed_count = %s,
                    success_count = %s,
                    failed_count = %s,
                    total_count = COALESCE(%s, total_count),
                    checkpoint = %s,
                    locked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (processed, success, failed, total, json.dumps(checkpoint), job_id),
            )
        else:
            cur.execute(
                """
                UPDATE collection_jobs SET
                    processed_count = %s,
                    success_count = %s,
                    failed_count = %s,
                    total_count = COALESCE(%s, total_count),
                    locked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (processed, success, failed, total, job_id),
            )
        conn.commit()


def complete_job(
    conn: psycopg.Connection, job_id: str, status: str = "completed"
) -> None:
    """작업 완료"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE collection_jobs SET
                status = %s,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (status, job_id),
        )
        conn.commit()


def update_query_stats(
    conn: psycopg.Connection, query_id: str, collected: int
) -> None:
    """검색 쿼리 통계 업데이트"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE search_queries SET
                total_collected = total_collected + %s,
                last_backfill_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (collected, query_id),
        )
        conn.commit()


def build_query(search_query: dict) -> str:
    """Europe PMC 검색 쿼리 생성"""
    query = search_query["query"]

    # OA 필터
    if search_query.get("open_access_only", True):
        query += " AND OPEN_ACCESS:Y"

    # 연도 필터
    year_from = search_query.get("year_from")
    year_to = search_query.get("year_to")
    if year_from or year_to:
        y_from = year_from or 1900
        y_to = year_to or 2099
        query += f" AND FIRST_PDATE:[{y_from} TO {y_to}]"

    return query


async def run_backfill_async(query_id: str, resume_job_id: str | None = None) -> dict:
    """Backfill 비동기 실행

    OAR-19/21 설계:
    - Connection Pool 사용 (동시성 안전)
    - Phase 1 (Search): Europe PMC 검색 → article_jobs에 등록
    - Phase 2 (Collect): pending 상태 article_jobs 처리

    Args:
        query_id: search_queries.id
        resume_job_id: 재개할 job_id (없으면 새로 생성)

    Returns:
        실행 결과 dict
    """
    # Connection Pool 획득 (싱글톤)
    pool = get_db_pool()

    # 1. 검색 쿼리 조회
    with pool.connection() as conn:
        search_query = get_search_query(conn, query_id)
        if not search_query:
            raise ValueError(f"Query not found or inactive: {query_id}")

        # 2. Europe PMC 쿼리 생성
        pmc_query = build_query(search_query)

        # 3. Job 생성 또는 재개
        if resume_job_id:
            job_id = resume_job_id
            logger.info(
                "backfill_resumed",
                job_id=job_id,
                query_id=query_id,
            )
        else:
            job_id = create_job(conn, query_id, pmc_query)
            logger.info(
                "backfill_started",
                job_id=job_id,
                query_id=query_id,
                query_name=search_query["name"],
                pmc_query=pmc_query,
            )

    # 4. Phase 1: Search - article_jobs에 등록
    if not resume_job_id:
        await _phase_search(pool, job_id, pmc_query, search_query)

    # 5. Phase 2: Collect - pending 상태 처리
    result = await _phase_collect(pool, job_id, query_id, search_query)

    return result


async def _phase_search(
    pool: ConnectionPool,
    job_id: str,
    pmc_query: str,
    search_query: dict,
) -> int:
    """Phase 1: 검색하여 article_jobs에 등록

    OAR-19 스타일: Connection Pool 사용
    """
    logger.info("search_phase_started", job_id=job_id)

    total_registered = 0
    page_batch = []
    batch_size = 100

    async with EuropePMCClient() as client:
        async for result in client.search_all(
            pmc_query,
            max_results=search_query.get("max_results"),
        ):
            page_batch.append({
                "pmcid": result.pmcid,
                "pmid": result.pmid,
                "doi": result.doi,
            })

            if len(page_batch) >= batch_size:
                with pool.connection() as conn:
                    batch_upsert_article_jobs(conn, job_id, page_batch)
                    total_registered += len(page_batch)

                    update_job_progress(
                        conn,
                        job_id,
                        processed=0,
                        success=0,
                        failed=0,
                        total=total_registered,
                        checkpoint={
                            "phase": "search",
                            "registered": total_registered,
                            "last_pmcid": result.pmcid,
                        },
                    )

                logger.info(
                    "search_phase_progress",
                    registered=total_registered,
                )

                page_batch = []

        # 남은 항목 등록
        if page_batch:
            with pool.connection() as conn:
                batch_upsert_article_jobs(conn, job_id, page_batch)
                total_registered += len(page_batch)

    # 검색 완료 체크포인트
    with pool.connection() as conn:
        update_job_progress(
            conn,
            job_id,
            processed=0,
            success=0,
            failed=0,
            total=total_registered,
            checkpoint={
                "phase": "collect",
                "total_articles": total_registered,
            },
        )

    logger.info(
        "search_phase_completed",
        job_id=job_id,
        total_registered=total_registered,
    )

    return total_registered


def check_paper_exists(conn, pmcid: str, pmid: str | None) -> bool:
    """papers 테이블에 이미 존재하는지 확인"""
    with conn.cursor() as cur:
        # pmcid 또는 pmid로 확인
        cur.execute(
            """
            SELECT 1 FROM papers
            WHERE pmcid = %s OR (pmid IS NOT NULL AND pmid = %s)
            LIMIT 1
            """,
            (pmcid, pmid),
        )
        return cur.fetchone() is not None


async def _process_single_article(
    client: EuropePMCClient,
    parser: XMLParser,
    db_storage: DatabaseStorage,
    s3_storage: S3Storage,
    error_storage: ErrorStorage,
    pool: ConnectionPool,
    job_id: str,
    article: dict,
) -> bool:
    """단일 논문 처리 (병렬 처리용)

    OAR-19 스타일: Connection Pool에서 연결 획득/반환
    """
    pmcid = article["pmcid"]
    pmid = article.get("pmid")
    doi = article.get("doi")
    xml = None

    try:
        # 이미 수집된 논문인지 확인 (중복 수집 방지)
        with pool.connection() as conn:
            if check_paper_exists(conn, pmcid, pmid):
                logger.info("paper_already_exists", pmcid=pmcid, pmid=pmid)
                update_article_status(conn, job_id, pmcid, "completed")
                return True  # 이미 있으면 성공으로 처리

        # downloading - Pool에서 연결 획득하여 상태 업데이트
        with pool.connection() as conn:
            update_article_status(conn, job_id, pmcid, "downloading")

        xml = await client.get_fulltext_xml(pmcid)

        if not xml:
            logger.warning(
                "no_xml_returned",
                pmcid=pmcid,
                pmid=pmid,
                doi=doi,
                base_url=client.base_url,
                expected_url=f"{client.base_url}/PMC{pmcid.replace('PMC', '')}/fullTextXML",
                rate_limiter_stats=client.get_stats(),
            )
            error_storage.log_error(ArticleError(
                job_id=job_id,
                stage="download",
                error_message="Fulltext XML not available",
                pmcid=pmcid,
                pmid=pmid,
                doi=doi,
                error_code="NO_XML",
                context={
                    "expected_url": f"{client.base_url}/PMC{pmcid.replace('PMC', '')}/fullTextXML",
                    "rate_limiter_stats": client.get_stats(),
                },
            ))
            with pool.connection() as conn:
                update_article_status(
                    conn, job_id, pmcid, "failed",
                    error_code="NO_XML",
                    error_msg="Fulltext XML not available",
                )
            return False

        # parsing
        with pool.connection() as conn:
            update_article_status(conn, job_id, pmcid, "parsing")

        try:
            paper = parser.parse(xml, pmcid)
        except Exception as parse_error:
            error_storage.log_exception(
                job_id=job_id,
                stage="parse",
                exc=parse_error,
                pmcid=pmcid,
                pmid=pmid,
                doi=doi,
                raw_response=xml[:10000] if xml else None,
            )
            raise

        # Search API에서 받은 식별자를 사용 (XML보다 우선)
        from ..models import Paper
        paper.pmcid = article.get("pmcid") or paper.pmcid
        paper.pmid = article.get("pmid") or paper.pmid
        paper.doi = article.get("doi") or paper.doi
        paper.paper_id = Paper.create_paper_id(paper.pmcid, paper.pmid)

        logger.debug(
            "paper_identifiers",
            pmcid=paper.pmcid,
            pmid=paper.pmid,
            doi=paper.doi,
        )

        # saving
        with pool.connection() as conn:
            update_article_status(conn, job_id, pmcid, "saving")

        try:
            s3_prefix = s3_storage.save_paper(paper)
            db_storage.save_paper(paper, s3_prefix)
        except Exception as save_error:
            error_storage.log_exception(
                job_id=job_id,
                stage="save",
                exc=save_error,
                pmcid=pmcid,
                pmid=pmid,
                doi=doi,
                context={"s3_prefix": s3_prefix if 's3_prefix' in dir() else None},
            )
            raise

        # completed
        with pool.connection() as conn:
            update_article_status(conn, job_id, pmcid, "completed")
        return True

    except Exception as e:
        logger.error(
            "article_failed",
            pmcid=pmcid,
            error=str(e),
        )
        with pool.connection() as conn:
            update_article_status(
                conn, job_id, pmcid, "failed",
                error_code="EXCEPTION",
                error_msg=str(e)[:500],
            )
        return False


async def _phase_collect(
    pool: ConnectionPool,
    job_id: str,
    query_id: str,
    search_query: dict,
) -> dict:
    """Phase 2: pending 상태 article_jobs 병렬 처리

    OAR-19 스타일: Connection Pool 공유
    - 각 태스크가 pool.connection()으로 연결 획득/반환
    - 동시성은 Pool의 max_size로 제어
    """
    max_concurrent = search_query.get("max_concurrent", 35)
    logger.info(
        "collect_phase_started",
        job_id=job_id,
        max_concurrent=max_concurrent,
    )

    parser = XMLParser()
    db_storage = DatabaseStorage()
    db_storage.connect()
    s3_storage = S3Storage()
    error_storage = ErrorStorage()
    error_storage.connect()

    try:
        async with EuropePMCClient(max_concurrent=max_concurrent) as client:
            while True:
                # pending 상태 논문 조회
                with pool.connection() as conn:
                    pending = get_pending_articles(conn, job_id, limit=max_concurrent)

                if not pending:
                    break

                # 병렬 처리: Pool을 공유
                tasks = [
                    _process_single_article(
                        client, parser, db_storage, s3_storage, error_storage,
                        pool, job_id, article
                    )
                    for article in pending
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                # 진행률 업데이트
                with pool.connection() as conn:
                    stats = get_article_job_stats(conn, job_id)
                    update_job_progress(
                        conn,
                        job_id,
                        processed=stats["completed"] + stats["failed"],
                        success=stats["completed"],
                        failed=stats["failed"],
                        total=stats["total"],
                    )

                logger.info(
                    "collect_phase_progress",
                    **stats,
                    batch_size=len(pending),
                )

        # 최종 통계 및 완료 처리
        with pool.connection() as conn:
            final_stats = get_article_job_stats(conn, job_id)
            status = "completed" if final_stats["pending"] == 0 else "partial"
            complete_job(conn, job_id, status)
            update_query_stats(conn, query_id, final_stats["completed"])

        result = {
            "job_id": job_id,
            "query_id": query_id,
            "query_name": search_query["name"],
            "total": final_stats["total"],
            "completed": final_stats["completed"],
            "failed": final_stats["failed"],
            "status": status,
        }

        logger.info("backfill_completed", **result)
        return result

    finally:
        db_storage.close()
        error_storage.close()


@app.task(bind=True, queue="backfill")
def run_backfill(self, query_id: str) -> dict:
    """Backfill 태스크 (Celery)

    Args:
        query_id: search_queries.id (UUID 문자열)

    Returns:
        실행 결과 dict
    """
    logger.info("backfill_task_started", query_id=query_id, task_id=self.request.id)

    try:
        result = asyncio.run(run_backfill_async(query_id))

        # 체이닝: 수집 성공 시 임베딩 자동 트리거
        if result.get("completed", 0) > 0:
            run_embed.delay(query_id)
            logger.info(
                "embed_triggered_after_backfill",
                query_id=query_id,
                collected_count=result.get("completed"),
            )

        return result

    except Exception as e:
        logger.error("backfill_task_failed", query_id=query_id, error=str(e))
        raise


@app.task(bind=True, queue="backfill")
def run_backfill_resume(self, query_id: str, job_id: str) -> dict:
    """Backfill Resume 태스크 (Celery)

    기존 job을 이어서 처리 (pending 상태 article_jobs만 처리)

    Args:
        query_id: search_queries.id (UUID 문자열)
        job_id: 재개할 collection_jobs.id

    Returns:
        실행 결과 dict
    """
    logger.info(
        "backfill_resume_started",
        query_id=query_id,
        job_id=job_id,
        task_id=self.request.id,
    )

    try:
        result = asyncio.run(run_backfill_async(query_id, resume_job_id=job_id))

        # 체이닝: 수집 성공 시 임베딩 자동 트리거
        if result.get("completed", 0) > 0:
            run_embed.delay(query_id)
            logger.info(
                "embed_triggered_after_backfill_resume",
                query_id=query_id,
                job_id=job_id,
                collected_count=result.get("completed"),
            )

        return result

    except Exception as e:
        logger.error(
            "backfill_resume_failed",
            query_id=query_id,
            job_id=job_id,
            error=str(e),
        )
        raise
