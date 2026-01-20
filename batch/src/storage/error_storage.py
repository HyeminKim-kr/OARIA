"""에러 로그 저장소

OAR-19 스타일: Connection Pool 사용
batch_errors 테이블에 에러 로그 저장
"""

import json
import traceback
from dataclasses import dataclass, field
from typing import Literal

from psycopg_pool import ConnectionPool
import structlog

from ..config import settings

logger = structlog.get_logger()

ErrorStage = Literal["search", "download", "parse", "save"]

# 모듈 레벨 싱글톤 Pool
_error_pool: ConnectionPool | None = None


def get_error_pool() -> ConnectionPool:
    """Error Storage용 Connection Pool 획득"""
    global _error_pool
    if _error_pool is None:
        _error_pool = ConnectionPool(
            conninfo=settings.db.dsn,
            min_size=2,
            max_size=20,
            open=True,
        )
        logger.info("error_pool_created", min_size=2, max_size=20)
    return _error_pool


@dataclass
class ArticleError:
    """에러 로그 데이터"""

    job_id: str
    stage: ErrorStage
    error_message: str
    pmcid: str | None = None
    pmid: str | None = None
    doi: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    raw_response: str | None = None
    context: dict | None = None


@dataclass
class ErrorStorage:
    """에러 로그 저장소 (Connection Pool 사용)"""

    _pool: ConnectionPool | None = field(default=None, repr=False)

    def connect(self) -> None:
        """Pool 연결"""
        self._pool = get_error_pool()

    def close(self) -> None:
        """Pool은 공유되므로 여기서 닫지 않음"""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def log_error(self, error: ArticleError) -> str:
        """에러 로그 저장

        Args:
            error: 에러 로그 데이터

        Returns:
            에러 로그 UUID
        """
        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    # context를 JSON 문자열로 변환
                    context_json = json.dumps(error.context) if error.context else None

                    cur.execute(
                        """
                        INSERT INTO batch_errors (
                            job_id, pmcid, pmid, doi,
                            stage, error_code, error_message, error_detail,
                            raw_response, context
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s::jsonb
                        )
                        RETURNING id
                        """,
                        (
                            error.job_id,
                            error.pmcid,
                            error.pmid,
                            error.doi,
                            error.stage,
                            error.error_code,
                            error.error_message,
                            error.error_detail,
                            error.raw_response,
                            context_json,
                        ),
                    )
                    error_id = cur.fetchone()[0]
                    conn.commit()

                    logger.debug(
                        "error_logged",
                        error_id=str(error_id),
                        stage=error.stage,
                        pmcid=error.pmcid,
                    )
                    return str(error_id)

            except Exception as e:
                conn.rollback()
                logger.warning(
                    "error_log_failed",
                    error=str(e),
                    original_error=error.error_message,
                )
                return ""

    def log_exception(
        self,
        job_id: str,
        stage: ErrorStage,
        exc: Exception,
        pmcid: str | None = None,
        pmid: str | None = None,
        doi: str | None = None,
        error_code: str | None = None,
        raw_response: str | None = None,
        context: dict | None = None,
    ) -> str:
        """예외를 에러 로그로 저장 (편의 메서드)

        Args:
            job_id: 배치 작업 ID
            stage: 에러 발생 단계
            exc: 예외 객체
            pmcid: PMC ID
            pmid: PubMed ID
            doi: DOI
            error_code: 에러 코드
            raw_response: 원본 응답
            context: 추가 컨텍스트

        Returns:
            에러 로그 UUID
        """
        error = ArticleError(
            job_id=job_id,
            stage=stage,
            error_message=str(exc),
            pmcid=pmcid,
            pmid=pmid,
            doi=doi,
            error_code=error_code or exc.__class__.__name__,
            error_detail=traceback.format_exc(),
            raw_response=raw_response[:10000] if raw_response else None,  # 10KB 제한
            context=context,
        )
        return self.log_error(error)
