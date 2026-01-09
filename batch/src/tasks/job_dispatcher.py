"""작업 Dispatch 및 복구 태스크

Celery Beat에서 주기적으로 실행:
1. dispatch_pending_jobs - 대기 큐의 작업을 워커에게 할당 (10초마다)
2. recover_stuck_jobs - Stuck 작업 감지 및 복구 (1분마다)
3. sync_jobs_from_db - DB와 Redis 동기화 (5분마다)
"""

import socket
from typing import Optional

import psycopg
import structlog
from psycopg_pool import ConnectionPool

from ..celery_app import app
from ..config import settings
from ..job_manager import get_job_manager, JobType, JobStatus

logger = structlog.get_logger()

# DB Pool (재사용)
_db_pool: Optional[ConnectionPool] = None


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
    return _db_pool


def get_worker_id() -> str:
    """현재 워커 식별자 생성"""
    hostname = socket.gethostname()
    return f"celery@{hostname}"


# ============================================================
# Dispatch 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def dispatch_pending_jobs(self):
    """대기 큐의 작업을 워커에게 dispatch

    Celery Beat에서 10초마다 실행.
    큐에서 작업을 꺼내 락을 획득하고, 실제 처리 태스크를 호출.
    """
    manager = get_job_manager()
    worker_id = get_worker_id()
    dispatched = 0
    skipped = 0

    # embed 타입 작업 처리
    while True:
        job_id = manager.pop_pending_job(JobType.EMBED)
        if not job_id:
            break

        # 작업 상태 확인
        state = manager.get_job_state(job_id, JobType.EMBED)
        if not state:
            logger.warning("dispatch_job_not_found", job_id=job_id)
            continue

        # 이미 처리 중이거나 완료된 작업은 스킵
        if state.get("status") in (JobStatus.PROCESSING, JobStatus.COMPLETED):
            logger.debug(
                "dispatch_job_skipped",
                job_id=job_id,
                status=state.get("status"),
            )
            skipped += 1
            continue

        # 락 획득 시도
        if not manager.acquire_lock(job_id, JobType.EMBED, worker_id):
            logger.debug("dispatch_lock_failed", job_id=job_id)
            # 락 획득 실패하면 다시 큐에 넣음
            manager.redis.rpush(manager._queue_key(JobType.EMBED), job_id)
            skipped += 1
            continue

        # 실제 작업 태스크 호출 (비동기)
        from .sample_embed import run_sample_embed_v2
        run_sample_embed_v2.delay(job_id)
        dispatched += 1

        logger.info(
            "job_dispatched",
            job_id=job_id,
            job_type=JobType.EMBED,
        )

    if dispatched > 0 or skipped > 0:
        logger.info(
            "dispatch_completed",
            dispatched=dispatched,
            skipped=skipped,
        )

    return {"dispatched": dispatched, "skipped": skipped}


# ============================================================
# 복구 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def recover_stuck_jobs(self):
    """Stuck 작업 감지 및 복구

    Celery Beat에서 1분마다 실행.
    Heartbeat가 오래된 작업을 감지하고 자동 재시도.
    """
    manager = get_job_manager()
    recovered = 0
    max_retries_exceeded = 0

    # embed 타입의 stuck 작업 찾기
    stuck_jobs = manager.get_stuck_jobs(JobType.EMBED)

    for job_id in stuck_jobs:
        if manager.recover_stuck_job(job_id, JobType.EMBED):
            recovered += 1
            logger.info("stuck_job_recovered", job_id=job_id)
        else:
            max_retries_exceeded += 1
            logger.warning(
                "stuck_job_max_retries",
                job_id=job_id,
            )

            # DB에도 실패 상태 동기화
            try:
                _sync_failed_to_db(job_id, "Max retries exceeded after stuck recovery")
            except Exception as e:
                logger.error("db_sync_failed", job_id=job_id, error=str(e))

    if recovered > 0 or max_retries_exceeded > 0:
        logger.info(
            "recovery_completed",
            recovered=recovered,
            max_retries_exceeded=max_retries_exceeded,
        )

    return {
        "recovered": recovered,
        "max_retries_exceeded": max_retries_exceeded,
    }


# ============================================================
# DB 동기화 태스크
# ============================================================


@app.task(bind=True, queue="embed")
def sync_jobs_from_db(self):
    """DB의 pending/processing 작업을 Redis와 동기화

    Celery Beat에서 5분마다 실행.
    Redis 장애 복구 또는 서버 재시작 시 DB 상태 복원.
    """
    manager = get_job_manager()
    pool = get_db_pool()
    synced = 0

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # pending 또는 processing 상태인 작업 조회
                cur.execute("""
                    SELECT id, status, paper_count, chunk_count,
                           error_message, created_at
                    FROM sample_embeddings
                    WHERE status IN ('pending', 'processing')
                    ORDER BY created_at
                """)

                for row in cur.fetchall():
                    job_id = str(row[0])
                    db_status = row[1]

                    # Redis에 이미 있으면 스킵
                    if manager.job_exists(job_id, JobType.EMBED):
                        continue

                    # DB 상태를 Redis로 동기화
                    db_data = {
                        "paper_count": row[2] or 0,
                        "chunk_count": row[3] or 0,
                        "error_message": row[4],
                        "created_at": row[5].isoformat() if row[5] else "",
                    }
                    manager.sync_from_db(job_id, JobType.EMBED, db_status, db_data)
                    synced += 1

        if synced > 0:
            logger.info("db_sync_completed", synced=synced)

    except Exception as e:
        logger.error("db_sync_error", error=str(e))

    return {"synced": synced}


# ============================================================
# 헬퍼 함수
# ============================================================


def _sync_failed_to_db(job_id: str, error_message: str) -> None:
    """실패 상태를 DB에 동기화"""
    pool = get_db_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sample_embeddings
                SET status = 'failed',
                    error_message = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (error_message, job_id))
            conn.commit()
