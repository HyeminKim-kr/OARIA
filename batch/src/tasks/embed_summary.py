"""요약 임베딩 태스크

논문 요약(PaperSummary)을 임베딩하여 Weaviate PaperChunk 컬렉션에 저장합니다.
기존 PaperChunk 컬렉션에 section='summary'로 저장하여 RAG 검색에 활용됩니다.

흐름:
1. paper_summaries 테이블에서 요약 조회
2. embedding_status를 'processing'으로 업데이트
3. OpenAI 임베딩 생성
4. Weaviate PaperChunk 컬렉션에 저장
5. embedding_status를 'completed'로 업데이트
"""

import uuid as uuid_module
from datetime import datetime, timezone
from typing import Optional

import psycopg
import structlog
from psycopg_pool import ConnectionPool

from ..celery_app import app
from ..config import settings
from ..embedding import EmbeddingClient, WeaviateClient

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
            min_size=1,
            max_size=5,
            open=True,
        )
        logger.info("embed_summary_db_pool_created", min_size=1, max_size=5)
    return _db_pool


def get_embedding_client() -> EmbeddingClient:
    """EmbeddingClient 인스턴스 생성"""
    return EmbeddingClient(
        api_key=settings.openai.api_key,
        model=settings.openai.embedding_model,
        dimensions=settings.openai.embedding_dimensions,
    )


def get_weaviate_client() -> WeaviateClient:
    """WeaviateClient 인스턴스 생성"""
    embedding_client = get_embedding_client()
    return WeaviateClient(
        host=settings.weaviate.host,
        port=settings.weaviate.port,
        embedding_client=embedding_client,
    )


# ============================================================
# 데이터베이스 함수
# ============================================================


def get_summary_by_id(conn: psycopg.Connection, summary_id: str) -> Optional[dict]:
    """요약 ID로 조회

    Args:
        conn: DB 연결
        summary_id: paper_summaries.id (UUID)

    Returns:
        요약 정보 dict 또는 None
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ps.id,
                ps.paper_id,
                ps.summary_type,
                ps.summary,
                ps.sections_used,
                ps.tokens_used,
                ps.embedding_status,
                p.paper_id as paper_id_str,
                p.pmcid,
                p.pmid,
                p.doi,
                p.title,
                p.journal,
                p.year,
                p.keywords
            FROM paper_summaries ps
            JOIN papers p ON p.id = ps.paper_id
            WHERE ps.id = %s
            """,
            (summary_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "paper_id": row[1],  # UUID
            "summary_type": row[2],
            "summary": row[3],
            "sections_used": row[4] or [],
            "tokens_used": row[5],
            "embedding_status": row[6],
            # Paper info
            "paper_id_str": row[7],  # VARCHAR (e.g., "pmc:PMC12345678")
            "pmcid": row[8],
            "pmid": row[9],
            "doi": row[10],
            "title": row[11],
            "journal": row[12],
            "year": row[13],
            "keywords": row[14] or [],
        }


def update_summary_embedding_status(
    conn: psycopg.Connection,
    summary_id: str,
    status: str,
    error_msg: Optional[str] = None,
) -> None:
    """요약의 임베딩 상태 업데이트"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE paper_summaries SET
                embedding_status = %s,
                embedding_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                datetime.now(timezone.utc) if status == "completed" else None,
                summary_id,
            ),
        )
        conn.commit()


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
# 임베딩 처리 함수
# ============================================================


def process_summary_embedding(
    pool: ConnectionPool,
    weaviate_client: WeaviateClient,
    summary: dict,
) -> dict:
    """요약 임베딩 처리

    Args:
        pool: DB Connection Pool
        weaviate_client: Weaviate 클라이언트
        summary: 요약 정보 dict

    Returns:
        {"success": bool, "error": str|None}
    """
    summary_id = str(summary["id"])
    paper_id_str = summary["paper_id_str"]

    try:
        # 1. 상태를 processing으로 업데이트
        with pool.connection() as conn:
            update_summary_embedding_status(conn, summary_id, "processing")
            authors = get_paper_authors(conn, str(summary["paper_id"]))

        # 2. 임베딩 입력 텍스트 구성
        # 요약 타입과 제목을 포함하여 컨텍스트 제공
        embedding_input = f"[{summary['summary_type'].upper()} SUMMARY] {summary['title']}\n\n{summary['summary']}"

        # 3. 임베딩 생성
        embedding = weaviate_client.embedding_client.embed_text(embedding_input)

        # 4. Weaviate에 저장
        # chunk_id는 summary 고유 ID 사용
        chunk_id = f"{paper_id_str}:summary:{summary['summary_type']}"
        object_uuid = str(uuid_module.uuid5(uuid_module.NAMESPACE_DNS, chunk_id))

        pmcid = summary.get("pmcid", "")
        source_url = f"https://europepmc.org/article/PMC/{pmcid}" if pmcid else None

        properties = {
            "paperId": paper_id_str,
            "chunkId": chunk_id,
            "embeddingVersion": weaviate_client.embedding_client.get_version_string(),
            "pmcid": pmcid,
            "pmid": summary.get("pmid"),
            "doi": summary.get("doi"),
            "title": summary.get("title", ""),
            "authors": authors,
            "journal": summary.get("journal"),
            "year": summary.get("year"),
            "keywords": summary.get("keywords", []),
            "section": "summary",  # 요약임을 표시
            "chunkIndex": 0,  # 요약은 단일 청크
            "content": summary["summary"],
            "offsetStart": 0,
            "offsetEnd": len(summary["summary"]),
            "textVersion": "v1",
            "sourceUrl": source_url,
            "createdAt": datetime.now(timezone.utc),
        }

        # 기존 객체가 있으면 삭제 후 삽입 (upsert)
        collection = weaviate_client.collection
        try:
            collection.data.delete_by_id(object_uuid)
        except Exception:
            pass  # 없으면 무시

        collection.data.insert(
            uuid=object_uuid,
            properties=properties,
            vector=embedding,
        )

        # 5. 상태 업데이트
        with pool.connection() as conn:
            update_summary_embedding_status(conn, summary_id, "completed")

        logger.info(
            "summary_embedded",
            summary_id=summary_id,
            paper_id=paper_id_str,
            summary_type=summary["summary_type"],
        )

        return {"success": True, "error": None}

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "summary_embedding_failed",
            summary_id=summary_id,
            error=error_msg,
        )

        try:
            with pool.connection() as conn:
                update_summary_embedding_status(conn, summary_id, "failed", error_msg)
        except Exception:
            pass  # 상태 업데이트 실패해도 계속 진행

        return {"success": False, "error": error_msg}


# ============================================================
# Celery 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def embed_summary_task(self, summary_id: str) -> dict:
    """요약 임베딩 태스크 (Celery)

    논문 요약을 임베딩하여 Weaviate에 저장합니다.

    Args:
        summary_id: paper_summaries.id (UUID string)

    Returns:
        실행 결과 dict
    """
    logger.info(
        "embed_summary_task_started",
        summary_id=summary_id,
        task_id=self.request.id,
    )

    pool = get_db_pool()
    weaviate_client = get_weaviate_client()

    try:
        # 1. 요약 조회
        with pool.connection() as conn:
            summary = get_summary_by_id(conn, summary_id)

        if not summary:
            logger.warning("summary_not_found", summary_id=summary_id)
            return {"success": False, "error": "Summary not found"}

        # 이미 완료된 경우 스킵
        if summary.get("embedding_status") == "completed":
            logger.info("summary_already_embedded", summary_id=summary_id)
            return {"success": True, "error": None, "skipped": True}

        # 2. 임베딩 처리
        result = process_summary_embedding(pool, weaviate_client, summary)

        return {
            "summary_id": summary_id,
            **result,
        }

    except Exception as e:
        error_msg = str(e)[:500]
        logger.error(
            "embed_summary_task_failed",
            summary_id=summary_id,
            error=error_msg,
        )
        return {"success": False, "error": error_msg}

    finally:
        weaviate_client.close()
