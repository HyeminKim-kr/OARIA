"""Backfill 태스크 (초기 적재)

OAR-21 설계 기반:
- search_queries에서 쿼리 조회
- Europe PMC 검색 → 전문 수집 → 파싱 → 저장
- batch_jobs 상태 관리
- batch_articles로 개별 논문 상태 관리
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
from ..collectors import (
    EuropePMCClient,
    should_collect,
    should_embed,
    parse_comment_correction,
    CollectAction,
    determine_collect_action,
)
from ..collectors.pmc_pdf import PMCPDFClient
from ..config import settings
from ..parsers import XMLParser
from ..storage import DatabaseStorage, S3Storage
from ..storage.error_storage import ArticleError, ErrorStorage

# 임베딩 관련 import (동시 실행용)
from .embed import (
    run_embed,
    get_papers_for_embedding,
    process_single_paper_async,
    get_async_embedding_client,
    get_db_pool as get_embed_db_pool,
)
from ..chunker import TextChunker
from ..embedding import WeaviateClient, EmbeddingClient

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
    """batch_articles에 논문 등록 (중복 시 무시)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO batch_articles (job_id, pmcid, pmid, doi, status)
            VALUES (%s, %s, %s, %s, 'pending')
            ON CONFLICT (job_id, pmcid) DO NOTHING
            """,
            (job_id, pmcid, pmid, doi),
        )


def batch_upsert_article_jobs(
    conn: psycopg.Connection,
    job_id: str,
    articles: list[dict],
) -> int:
    """batch_articles에 배치로 논문 등록

    Args:
        conn: DB 연결
        job_id: 배치 작업 ID
        articles: 논문 목록 (pmcid, pmid, doi, metadata 포함)

    Returns:
        등록된 논문 수
    """
    if not articles:
        return 0

    with conn.cursor() as cur:
        # psycopg3에서는 executemany 사용
        # metadata 컬럼 추가 (JSONB)
        cur.executemany(
            """
            INSERT INTO batch_articles (job_id, pmcid, pmid, doi, status, metadata)
            VALUES (%s, %s, %s, %s, 'pending', %s)
            ON CONFLICT (job_id, pmcid) DO NOTHING
            """,
            [
                (
                    job_id,
                    a["pmcid"],
                    a.get("pmid"),
                    a.get("doi"),
                    json.dumps(a.get("metadata")) if a.get("metadata") else None,
                )
                for a in articles
            ],
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
    """batch_articles 상태 업데이트"""
    with conn.cursor() as cur:
        if status == "failed":
            # 실패 시 재시도 설정 (attempt_count < max_attempts이면)
            cur.execute(
                """
                UPDATE batch_articles SET
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
                WHERE job_id = %s AND pmcid = %s
                """,
                (error_code, error_msg, job_id, pmcid),
            )
        else:
            cur.execute(
                """
                UPDATE batch_articles SET
                    status = %s,
                    updated_at = NOW()
                WHERE job_id = %s AND pmcid = %s
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
            SELECT pmcid, pmid, doi, metadata
            FROM batch_articles
            WHERE job_id = %s
              AND status = 'pending'
              AND (next_run_at IS NULL OR next_run_at <= NOW())
            ORDER BY created_at
            LIMIT %s
            """,
            (job_id, limit),
        )
        return [
            {
                "pmcid": row[0],
                "pmid": row[1],
                "doi": row[2],
                "metadata": row[3] if row[3] else {},
            }
            for row in cur.fetchall()
        ]


def get_article_job_stats(conn: psycopg.Connection, job_id: str) -> dict:
    """batch_articles 통계 조회"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status IN ('downloading', 'parsing', 'saving')) as in_progress
            FROM batch_articles
            WHERE job_id = %s
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


def check_job_cancelled(conn: psycopg.Connection, job_id: str) -> bool:
    """Job이 cancelled 상태인지 확인"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status FROM batch_jobs WHERE id = %s
            """,
            (job_id,),
        )
        row = cur.fetchone()
        return row is not None and row[0] == "cancelled"


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
    """batch_jobs 생성"""
    import socket
    worker_id = socket.gethostname()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO batch_jobs (
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
                UPDATE batch_jobs SET
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
                UPDATE batch_jobs SET
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


def update_job_total_only(
    conn: psycopg.Connection,
    job_id: str,
    total: int,
    checkpoint: dict | None = None,
) -> None:
    """총 개수만 업데이트 (진행률은 건드리지 않음)

    Search Phase에서 사용 - Collect의 진행률을 덮어쓰지 않도록
    """
    with conn.cursor() as cur:
        if checkpoint:
            cur.execute(
                """
                UPDATE batch_jobs SET
                    total_count = %s,
                    checkpoint = %s,
                    locked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (total, json.dumps(checkpoint), job_id),
            )
        else:
            cur.execute(
                """
                UPDATE batch_jobs SET
                    total_count = %s,
                    locked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (total, job_id),
            )
        conn.commit()


def complete_job(
    conn: psycopg.Connection, job_id: str, status: str = "completed"
) -> None:
    """작업 완료"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE batch_jobs SET
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

    OAR-19/21 설계 + Producer-Consumer 패턴:
    - Connection Pool 사용 (동시성 안전)
    - Phase 1 (Search): Europe PMC 검색 → batch_articles에 등록 [Producer]
    - Phase 2 (Collect): pending 상태 batch_articles 처리 [Consumer]
    - 두 Phase가 동시에 실행되어 검색된 논문을 바로 수집

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

    # Resume 모드: Collect + Embed 실행 (이미 Search 완료됨)
    if resume_job_id:
        search_done = asyncio.Event()
        search_done.set()  # 이미 검색 완료됨
        collect_done = asyncio.Event()

        async def resume_collect():
            result = await _phase_collect(pool, job_id, query_id, search_query, search_done)
            collect_done.set()
            return result

        async def resume_embed():
            return await _phase_embed(pool, job_id, query_id, collect_done)

        collect_result, embed_result = await asyncio.gather(resume_collect(), resume_embed())
        collect_result["embedded"] = embed_result.get("embedded", 0)
        collect_result["embed_failed"] = embed_result.get("failed", 0)
        return collect_result

    # Producer-Consumer 패턴: Search, Collect, Embed 동시 실행
    search_done = asyncio.Event()
    collect_done = asyncio.Event()
    search_result = {"registered": 0, "dropped": 0, "total_searched": 0}

    async def producer():
        """Phase 1: 검색하여 batch_articles에 등록 (Producer)"""
        nonlocal search_result
        try:
            search_result = await _phase_search(pool, job_id, pmc_query, search_query)
        finally:
            search_done.set()  # 검색 완료 (성공/실패 모두)
            logger.info("search_producer_done", job_id=job_id)

    async def collect_consumer():
        """Phase 2: pending 상태 처리 (Collect Consumer)"""
        try:
            return await _phase_collect(pool, job_id, query_id, search_query, search_done)
        finally:
            collect_done.set()  # 수집 완료
            logger.info("collect_consumer_done", job_id=job_id)

    async def embed_consumer():
        """Phase 3: 수집된 논문 임베딩 (Embed Consumer)"""
        return await _phase_embed(pool, job_id, query_id, collect_done)

    # 동시 실행: Search, Collect, Embed
    logger.info(
        "concurrent_execution_started",
        job_id=job_id,
        mode="triple_producer_consumer",
    )

    _, collect_result, embed_result = await asyncio.gather(
        producer(), collect_consumer(), embed_consumer()
    )

    # 결과 병합
    collect_result["embedded"] = embed_result.get("embedded", 0)
    collect_result["embed_failed"] = embed_result.get("failed", 0)

    return collect_result


async def _phase_search(
    pool: ConnectionPool,
    job_id: str,
    pmc_query: str,
    search_query: dict,
) -> dict:
    """Phase 1: 검색하여 batch_articles에 등록

    OAR-19 스타일: Connection Pool 사용
    pubType 기반 필터링 적용

    Returns:
        dict: {registered: int, dropped: int, total_searched: int}
    """
    logger.info("search_phase_started", job_id=job_id)

    stats = {"registered": 0, "dropped": 0, "total_searched": 0}
    page_batch = []
    batch_size = 100

    async with EuropePMCClient() as client:
        async for result in client.search_all(
            pmc_query,
            max_results=search_query.get("max_results"),
        ):
            stats["total_searched"] += 1

            # pubType 필터링: DROP 타입은 제외
            if not should_collect(result.pub_types):
                stats["dropped"] += 1
                logger.debug(
                    "article_dropped_by_pub_type",
                    pmcid=result.pmcid,
                    pub_types=result.pub_types,
                )
                continue

            # comment_corrections를 dict 리스트로 변환
            cc_list = [
                {
                    "id": cc.id,
                    "type": cc.type,
                    "source": cc.source,
                    "reference": cc.reference,
                }
                for cc in result.comment_corrections
            ]

            page_batch.append({
                "pmcid": result.pmcid,
                "pmid": result.pmid,
                "doi": result.doi,
                "metadata": {
                    "pub_types": result.pub_types,
                    "comment_corrections": cc_list,
                },
            })

            if len(page_batch) >= batch_size:
                with pool.connection() as conn:
                    batch_upsert_article_jobs(conn, job_id, page_batch)
                    stats["registered"] += len(page_batch)

                    # total만 업데이트 (진행률은 건드리지 않음 - Race Condition 방지)
                    update_job_total_only(
                        conn,
                        job_id,
                        total=stats["registered"],
                        checkpoint={
                            "phase": "search",
                            "registered": stats["registered"],
                            "dropped": stats["dropped"],
                            "total_searched": stats["total_searched"],
                            "last_pmcid": result.pmcid,
                        },
                    )

                logger.info(
                    "search_phase_progress",
                    **stats,
                )

                page_batch = []

        # 남은 항목 등록
        if page_batch:
            with pool.connection() as conn:
                batch_upsert_article_jobs(conn, job_id, page_batch)
                stats["registered"] += len(page_batch)

    # 검색 완료 체크포인트 (total만 업데이트)
    with pool.connection() as conn:
        update_job_total_only(
            conn,
            job_id,
            total=stats["registered"],
            checkpoint={
                "phase": "collect",
                **stats,
            },
        )

    logger.info(
        "search_phase_completed",
        job_id=job_id,
        **stats,
    )

    return stats


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
    pdf_client: PMCPDFClient | None = None,
) -> bool:
    """단일 논문 처리 (병렬 처리용)

    OAR-19 스타일: Connection Pool에서 연결 획득/반환
    pubType 및 관계 처리 포함
    """
    pmcid = article["pmcid"]
    pmid = article.get("pmid")
    doi = article.get("doi")
    metadata = article.get("metadata", {})
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

        # pub_types 및 관계 처리
        _process_paper_metadata(db_storage, pmid, metadata)

        # PDF 다운로드 (설정 활성화 시)
        if settings.collection.collect_pdf and pdf_client:
            await _download_and_save_pdf(
                pdf_client, s3_storage, db_storage, pmcid, paper.paper_id
            )

        # Citations/References 수집 (설정 활성화 시)
        if settings.collection.collect_citations:
            await _collect_citations_and_references(
                client, db_storage, pmcid, paper.paper_id
            )

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


def _process_paper_metadata(
    db_storage: DatabaseStorage,
    pmid: str | None,
    metadata: dict,
) -> None:
    """논문 메타데이터 처리 (pub_types, 관계)

    Args:
        db_storage: DB 저장소
        pmid: 현재 논문 PMID
        metadata: Search API에서 수집한 메타데이터
    """
    if not pmid:
        return

    # 1. pub_types 업데이트
    pub_types = metadata.get("pub_types", [])
    if pub_types:
        db_storage.update_paper_pub_types(pmid, pub_types)

    # 2. 관계 처리
    comment_corrections = metadata.get("comment_corrections", [])
    if comment_corrections:
        # 관계 파싱
        parsed_relations = []
        for cc in comment_corrections:
            parsed = parse_comment_correction(cc, pmid)
            if parsed:
                parsed_relations.append(parsed)

        # 관계 저장 및 플래그 업데이트
        if parsed_relations:
            db_storage.process_paper_relations(pmid, parsed_relations)


async def _download_and_save_pdf(
    pdf_client: PMCPDFClient,
    s3_storage: S3Storage,
    db_storage: DatabaseStorage,
    pmcid: str,
    paper_id: str,
) -> bool:
    """PDF 다운로드 및 저장

    Args:
        pdf_client: PMC PDF 클라이언트
        s3_storage: S3 저장소
        db_storage: DB 저장소
        pmcid: PMC ID
        paper_id: 논문 ID

    Returns:
        성공 여부
    """
    try:
        result = await pdf_client.download_pdf(pmcid)
        if not result:
            logger.debug("pdf_not_available", pmcid=pmcid)
            return False

        pdf_bytes, size = result

        # S3에 저장
        s3_key, pdf_size, pdf_hash = s3_storage.save_pdf(paper_id, pdf_bytes)

        # DB 업데이트
        db_storage.update_paper_pdf_info(paper_id, pdf_size, pdf_hash)

        logger.info(
            "pdf_saved",
            pmcid=pmcid,
            paper_id=paper_id,
            size=pdf_size,
        )
        return True

    except Exception as e:
        logger.warning(
            "pdf_download_failed",
            pmcid=pmcid,
            paper_id=paper_id,
            error=str(e),
        )
        return False


async def _collect_citations_and_references(
    pmc_client: EuropePMCClient,
    db_storage: DatabaseStorage,
    pmcid: str,
    paper_id: str,
) -> dict:
    """Citations/References 수집

    Args:
        pmc_client: Europe PMC 클라이언트
        db_storage: DB 저장소
        pmcid: PMC ID
        paper_id: 논문 ID

    Returns:
        수집 결과 {citations: int, references: int}
    """
    result = {"citations": 0, "references": 0}

    try:
        # 1. Citations 수집 (이 논문을 인용한 논문들)
        citations_page = await pmc_client.get_citations(
            pmcid,
            page_size=settings.collection.max_citations,
        )

        for citation in citations_page.results:
            # source: 인용한 논문 (citation), target: 현재 논문
            source_id = _build_paper_id(citation.pmcid, citation.pmid)
            if source_id and source_id != paper_id:
                saved = db_storage.save_citation(
                    source_paper_id=source_id,
                    target_paper_id=paper_id,
                    source_pmcid=citation.pmcid,
                    source_pmid=citation.pmid,
                    target_pmcid=pmcid,
                    target_pmid=None,  # 현재 논문의 pmid
                    collected_from=paper_id,
                )
                if saved:
                    result["citations"] += 1

        # 2. References 수집 (이 논문이 인용한 논문들)
        references_page = await pmc_client.get_references(
            pmcid,
            page_size=settings.collection.max_references,
        )

        for reference in references_page.results:
            # source: 현재 논문, target: 인용된 논문 (reference)
            target_id = _build_paper_id(reference.pmcid, reference.pmid)
            if target_id and target_id != paper_id:
                saved = db_storage.save_citation(
                    source_paper_id=paper_id,
                    target_paper_id=target_id,
                    source_pmcid=pmcid,
                    source_pmid=None,  # 현재 논문의 pmid
                    target_pmcid=reference.pmcid,
                    target_pmid=reference.pmid,
                    collected_from=paper_id,
                )
                if saved:
                    result["references"] += 1

        # 3. DB에 통계 업데이트
        db_storage.update_citation_counts(paper_id)

        logger.info(
            "citations_collected",
            pmcid=pmcid,
            paper_id=paper_id,
            citations=result["citations"],
            references=result["references"],
        )

    except Exception as e:
        logger.warning(
            "citations_collection_failed",
            pmcid=pmcid,
            paper_id=paper_id,
            error=str(e),
        )

    return result


def _build_paper_id(pmcid: str | None, pmid: str | None) -> str | None:
    """paper_id 생성 (pmcid 또는 pmid 기반)"""
    if pmcid:
        clean_pmcid = pmcid.replace("PMC", "") if pmcid.startswith("PMC") else pmcid
        return f"pmc:PMC{clean_pmcid}"
    elif pmid:
        return f"pmid:{pmid}"
    return None


async def _phase_collect(
    pool: ConnectionPool,
    job_id: str,
    query_id: str,
    search_query: dict,
    search_done: asyncio.Event | None = None,
) -> dict:
    """Phase 2: pending 상태 batch_articles 병렬 처리

    OAR-19 스타일: Connection Pool 공유 + Producer-Consumer 패턴
    - 각 태스크가 pool.connection()으로 연결 획득/반환
    - 동시성은 Pool의 max_size로 제어
    - search_done 이벤트로 검색 완료 여부 확인

    Args:
        pool: Connection Pool
        job_id: 작업 ID
        query_id: 검색 쿼리 ID
        search_query: 검색 쿼리 설정
        search_done: 검색 완료 이벤트 (None이면 즉시 완료로 간주)
    """
    max_concurrent = search_query.get("max_concurrent", 35)
    logger.info(
        "collect_phase_started",
        job_id=job_id,
        max_concurrent=max_concurrent,
        mode="consumer" if search_done else "standalone",
    )

    parser = XMLParser()
    db_storage = DatabaseStorage()
    db_storage.connect()
    s3_storage = S3Storage()
    error_storage = ErrorStorage()
    error_storage.connect()

    # PDF 클라이언트 (설정에 따라 활성화)
    pdf_client: PMCPDFClient | None = None

    # 빈 폴링 대기 시간 (Producer-Consumer 모드에서 검색 대기)
    POLL_INTERVAL = 2.0  # 2초
    empty_poll_count = 0
    MAX_EMPTY_POLLS = 3  # 검색 완료 후 연속 3번 빈 결과면 종료

    try:
        async with EuropePMCClient(max_concurrent=max_concurrent) as client:
            # PDF 수집 활성화 시 PDF 클라이언트 생성
            if settings.collection.collect_pdf:
                pdf_client = PMCPDFClient(
                    max_pdf_size=settings.collection.max_pdf_size,
                )
                await pdf_client.__aenter__()
            while True:
                # Job cancelled 상태 체크 (Admin에서 취소 시)
                with pool.connection() as conn:
                    if check_job_cancelled(conn, job_id):
                        logger.info(
                            "job_cancelled_by_user",
                            job_id=job_id,
                        )
                        break

                # pending 상태 논문 조회
                with pool.connection() as conn:
                    pending = get_pending_articles(conn, job_id, limit=max_concurrent)

                if not pending:
                    # Producer-Consumer 모드: 검색 완료 여부에 따라 대기/종료
                    if search_done is None:
                        # 단독 모드: 즉시 종료
                        break

                    if search_done.is_set():
                        # 검색 완료됨: 연속 빈 결과 카운트
                        empty_poll_count += 1
                        if empty_poll_count >= MAX_EMPTY_POLLS:
                            logger.info(
                                "collect_phase_no_more_pending",
                                job_id=job_id,
                                empty_polls=empty_poll_count,
                            )
                            break
                        # 잠시 대기 후 재확인 (마지막 배치가 등록 중일 수 있음)
                        await asyncio.sleep(POLL_INTERVAL)
                        continue
                    else:
                        # 검색 진행 중: 대기 후 재시도
                        logger.debug(
                            "collect_waiting_for_search",
                            job_id=job_id,
                        )
                        await asyncio.sleep(POLL_INTERVAL)
                        continue

                # 처리할 논문이 있으면 빈 폴링 카운트 리셋
                empty_poll_count = 0

                # 병렬 처리: Pool을 공유
                tasks = [
                    _process_single_article(
                        client, parser, db_storage, s3_storage, error_storage,
                        pool, job_id, article, pdf_client
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
                    search_done=search_done.is_set() if search_done else True,
                )

        # 최종 통계 및 완료 처리
        with pool.connection() as conn:
            final_stats = get_article_job_stats(conn, job_id)

            # cancelled 상태면 상태 변경하지 않음 (이미 Admin에서 변경됨)
            if check_job_cancelled(conn, job_id):
                status = "cancelled"
                logger.info(
                    "backfill_stopped_by_cancel",
                    job_id=job_id,
                    **final_stats,
                )
            else:
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
        # PDF 클라이언트 정리
        if pdf_client:
            await pdf_client.__aexit__(None, None, None)
        db_storage.close()
        error_storage.close()


async def _phase_embed(
    pool: ConnectionPool,
    job_id: str,
    query_id: str,
    collect_done: asyncio.Event,
    max_concurrent: int = 5,
) -> dict:
    """Phase 3: 수집된 논문 임베딩 (Consumer)

    수집과 동시에 실행되어 수집된 논문을 바로 임베딩합니다.

    Args:
        pool: Connection Pool
        job_id: 배치 작업 ID
        query_id: 검색 쿼리 ID
        collect_done: 수집 완료 이벤트
        max_concurrent: 동시 임베딩 수

    Returns:
        dict: {embedded: int, failed: int}
    """
    logger.info(
        "embed_phase_started",
        job_id=job_id,
        query_id=query_id,
        max_concurrent=max_concurrent,
    )

    stats = {"embedded": 0, "failed": 0}

    # 빈 폴링 대기 설정
    POLL_INTERVAL = 3.0  # 3초 (임베딩이 더 무거우므로)
    empty_poll_count = 0
    MAX_EMPTY_POLLS = 5  # 수집 완료 후 5회 빈 결과면 종료

    # 리소스 초기화
    s3_storage = S3Storage()
    chunker = TextChunker()
    embedding_client = get_async_embedding_client()

    # Weaviate 연결 (WeaviateClient는 __init__에서 자동 연결)
    weaviate_client = WeaviateClient(
        host=settings.weaviate.host,
        port=settings.weaviate.port,
        embedding_client=EmbeddingClient(
            api_key=settings.openai.api_key,
            model=settings.openai.embedding_model,
            dimensions=settings.openai.embedding_dimensions,
        ),
    )
    collection = weaviate_client.collection  # property로 접근

    try:
        while True:
            # Job cancelled 상태 체크
            with pool.connection() as conn:
                if check_job_cancelled(conn, job_id):
                    logger.info("embed_phase_cancelled", job_id=job_id)
                    break

            # 임베딩 대기 논문 조회 (embedding_status IS NULL)
            with pool.connection() as conn:
                papers = get_papers_for_embedding(
                    conn, query_id, limit=max_concurrent, status_filter="pending"
                )

            if not papers:
                # 수집 완료 여부에 따라 대기/종료
                if collect_done.is_set():
                    empty_poll_count += 1
                    if empty_poll_count >= MAX_EMPTY_POLLS:
                        logger.info(
                            "embed_phase_no_more_papers",
                            job_id=job_id,
                            empty_polls=empty_poll_count,
                        )
                        break
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                else:
                    # 수집 진행 중: 대기 후 재시도
                    logger.debug("embed_waiting_for_collect", job_id=job_id)
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

            # 처리할 논문이 있으면 카운트 리셋
            empty_poll_count = 0

            # 병렬 임베딩 처리
            tasks = [
                process_single_paper_async(
                    pool, s3_storage, collection, embedding_client, chunker, paper
                )
                for paper in papers
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    stats["failed"] += 1
                    logger.error("embed_task_exception", error=str(result))
                elif result.get("success"):
                    stats["embedded"] += 1
                else:
                    stats["failed"] += 1

            logger.info(
                "embed_phase_progress",
                job_id=job_id,
                batch_size=len(papers),
                **stats,
                collect_done=collect_done.is_set(),
            )

    except Exception as e:
        logger.error("embed_phase_error", job_id=job_id, error=str(e))

    finally:
        await embedding_client.close()
        weaviate_client.close()

    logger.info("embed_phase_completed", job_id=job_id, **stats)
    return stats


@app.task(bind=True, queue="backfill")
def run_backfill(self, query_id: str) -> dict:
    """Backfill 태스크 (Celery)

    Search → Collect → Embed 가 모두 동시에 실행됩니다.
    (Producer-Consumer 패턴)

    Args:
        query_id: search_queries.id (UUID 문자열)

    Returns:
        실행 결과 dict (embedded, embed_failed 포함)
    """
    logger.info("backfill_task_started", query_id=query_id, task_id=self.request.id)

    try:
        result = asyncio.run(run_backfill_async(query_id))

        logger.info(
            "backfill_task_completed",
            query_id=query_id,
            collected=result.get("completed"),
            embedded=result.get("embedded"),
        )

        return result

    except Exception as e:
        logger.error("backfill_task_failed", query_id=query_id, error=str(e))
        raise


@app.task(bind=True, queue="backfill")
def run_backfill_resume(self, query_id: str, job_id: str) -> dict:
    """Backfill Resume 태스크 (Celery)

    기존 job을 이어서 처리 (Collect + Embed 동시 실행)

    Args:
        query_id: search_queries.id (UUID 문자열)
        job_id: 재개할 batch_jobs.id

    Returns:
        실행 결과 dict (embedded, embed_failed 포함)
    """
    logger.info(
        "backfill_resume_started",
        query_id=query_id,
        job_id=job_id,
        task_id=self.request.id,
    )

    try:
        result = asyncio.run(run_backfill_async(query_id, resume_job_id=job_id))

        logger.info(
            "backfill_resume_completed",
            query_id=query_id,
            job_id=job_id,
            collected=result.get("completed"),
            embedded=result.get("embedded"),
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
