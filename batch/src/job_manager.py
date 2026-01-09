"""Redis 기반 작업 상태 관리

작업 생명주기:
1. create_job() - 작업 생성, 큐에 추가
2. acquire_lock() - 분산 락 획득 (중복 실행 방지)
3. start_job() - 작업 시작, heartbeat 시작
4. update_progress() - 진행률 업데이트 + heartbeat 갱신
5. complete_job() / fail_job() - 작업 완료/실패

상태 전이:
pending → queued → processing → completed/failed
                              ↘ (retry) → queued
"""

from datetime import datetime, timezone as tz
from typing import Optional, Any
import json

import redis
import structlog

from .config import settings

logger = structlog.get_logger()


class JobStatus:
    """작업 상태 상수"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType:
    """작업 유형 상수"""
    EMBED = "embed"  # 샘플 임베딩


class JobStateManager:
    """Redis 기반 작업 상태 관리자

    Redis 키 구조:
    - job:{type}:{id}:state - Hash (상태, 진행률, heartbeat 등)
    - job:{type}:{id}:lock - String (분산 락, 워커 ID)
    - queue:{type}:pending - List (대기 중인 작업 ID)
    """

    HEARTBEAT_INTERVAL = 30  # 초 - heartbeat 갱신 주기
    HEARTBEAT_TIMEOUT = 120  # 초 - 이 시간 지나면 stuck으로 간주
    LOCK_TIMEOUT = 600  # 초 - 락 만료 시간 (10분)
    MAX_RETRIES = 3  # 최대 재시도 횟수

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                decode_responses=True,
            )

    def _state_key(self, job_type: str, job_id: str) -> str:
        return f"job:{job_type}:{job_id}:state"

    def _lock_key(self, job_type: str, job_id: str) -> str:
        return f"job:{job_type}:{job_id}:lock"

    def _queue_key(self, job_type: str) -> str:
        return f"queue:{job_type}:pending"

    # ============================================================
    # 작업 생성/조회
    # ============================================================

    def create_job(
        self,
        job_id: str,
        job_type: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """작업 생성 및 큐에 추가

        Args:
            job_id: 작업 ID (DB의 sample_embeddings.id)
            job_type: 작업 유형 (embed 등)
            metadata: 추가 메타데이터
        """
        state_key = self._state_key(job_type, job_id)
        queue_key = self._queue_key(job_type)

        state = {
            "status": JobStatus.QUEUED,
            "progress": 0,
            "total": 0,
            "retry_count": 0,
            "error": "",
            "worker_id": "",
            "created_at": datetime.now(tz.utc).isoformat(),
            "queued_at": datetime.now(tz.utc).isoformat(),
            "started_at": "",
            "completed_at": "",
            "heartbeat": "",
        }
        if metadata:
            state.update(metadata)

        # 상태 저장 + 큐에 추가 (atomic)
        pipe = self.redis.pipeline()
        pipe.hset(state_key, mapping=state)
        pipe.rpush(queue_key, job_id)
        pipe.execute()

        logger.info(
            "job_created",
            job_id=job_id,
            job_type=job_type,
        )

    def get_job_state(self, job_id: str, job_type: str) -> Optional[dict]:
        """작업 상태 조회

        Returns:
            작업 상태 dict 또는 None
        """
        state_key = self._state_key(job_type, job_id)
        state = self.redis.hgetall(state_key)

        if not state:
            return None

        # 숫자 필드 변환
        for field in ["progress", "total", "retry_count"]:
            if field in state:
                state[field] = int(state[field])

        return state

    def job_exists(self, job_id: str, job_type: str) -> bool:
        """작업이 Redis에 존재하는지 확인"""
        state_key = self._state_key(job_type, job_id)
        return self.redis.exists(state_key) > 0

    # ============================================================
    # 분산 락
    # ============================================================

    def acquire_lock(
        self,
        job_id: str,
        job_type: str,
        worker_id: str,
    ) -> bool:
        """분산 락 획득 (중복 실행 방지)

        Args:
            job_id: 작업 ID
            job_type: 작업 유형
            worker_id: 워커 식별자

        Returns:
            락 획득 성공 여부
        """
        lock_key = self._lock_key(job_type, job_id)

        # NX: 키가 없을 때만 설정, EX: 만료 시간
        acquired = self.redis.set(
            lock_key, worker_id, nx=True, ex=self.LOCK_TIMEOUT
        )

        if acquired:
            logger.debug("lock_acquired", job_id=job_id, worker_id=worker_id)
        else:
            current_holder = self.redis.get(lock_key)
            logger.debug(
                "lock_not_acquired",
                job_id=job_id,
                worker_id=worker_id,
                current_holder=current_holder,
            )

        return bool(acquired)

    def release_lock(self, job_id: str, job_type: str, worker_id: str) -> bool:
        """분산 락 해제 (자신이 보유한 경우만)

        Returns:
            락 해제 성공 여부
        """
        lock_key = self._lock_key(job_type, job_id)

        # Lua script로 atomic하게 확인 후 삭제
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = self.redis.eval(script, 1, lock_key, worker_id)
        return bool(result)

    def force_release_lock(self, job_id: str, job_type: str) -> bool:
        """분산 락 강제 해제 (복구용)"""
        lock_key = self._lock_key(job_type, job_id)
        return bool(self.redis.delete(lock_key))

    def extend_lock(self, job_id: str, job_type: str, worker_id: str) -> bool:
        """락 만료 시간 연장"""
        lock_key = self._lock_key(job_type, job_id)

        # 자신이 보유한 락인지 확인 후 연장
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = self.redis.eval(
            script, 1, lock_key, worker_id, self.LOCK_TIMEOUT
        )
        return bool(result)

    # ============================================================
    # 작업 상태 전이
    # ============================================================

    def start_job(
        self,
        job_id: str,
        job_type: str,
        worker_id: str,
        total: int = 0,
    ) -> None:
        """작업 시작 (processing 상태로 전환)

        Args:
            job_id: 작업 ID
            job_type: 작업 유형
            worker_id: 워커 식별자
            total: 전체 처리 대상 수
        """
        state_key = self._state_key(job_type, job_id)
        now = datetime.now(tz.utc).isoformat()

        self.redis.hset(state_key, mapping={
            "status": JobStatus.PROCESSING,
            "worker_id": worker_id,
            "total": total,
            "started_at": now,
            "heartbeat": now,
        })

        logger.info(
            "job_started",
            job_id=job_id,
            job_type=job_type,
            worker_id=worker_id,
            total=total,
        )

    def update_progress(
        self,
        job_id: str,
        job_type: str,
        progress: int,
        total: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """진행률 업데이트 + heartbeat 갱신

        Args:
            job_id: 작업 ID
            job_type: 작업 유형
            progress: 현재 진행 수
            total: 전체 수 (변경 시)
            extra: 추가 필드 (chunk_count 등)
        """
        state_key = self._state_key(job_type, job_id)
        now = datetime.now(tz.utc).isoformat()

        updates = {
            "progress": progress,
            "heartbeat": now,
        }
        if total is not None:
            updates["total"] = total
        if extra:
            updates.update(extra)

        self.redis.hset(state_key, mapping=updates)

    def complete_job(
        self,
        job_id: str,
        job_type: str,
        worker_id: str,
        result: Optional[dict] = None,
    ) -> None:
        """작업 완료 처리

        Args:
            job_id: 작업 ID
            job_type: 작업 유형
            worker_id: 워커 식별자
            result: 결과 메타데이터
        """
        state_key = self._state_key(job_type, job_id)
        now = datetime.now(tz.utc).isoformat()

        updates = {
            "status": JobStatus.COMPLETED,
            "completed_at": now,
            "error": "",
        }
        if result:
            # result를 JSON으로 저장
            updates["result"] = json.dumps(result)

        self.redis.hset(state_key, mapping=updates)
        self.release_lock(job_id, job_type, worker_id)

        logger.info(
            "job_completed",
            job_id=job_id,
            job_type=job_type,
        )

    def fail_job(
        self,
        job_id: str,
        job_type: str,
        worker_id: str,
        error: str,
    ) -> None:
        """작업 실패 처리

        Args:
            job_id: 작업 ID
            job_type: 작업 유형
            worker_id: 워커 식별자
            error: 에러 메시지
        """
        state_key = self._state_key(job_type, job_id)
        now = datetime.now(tz.utc).isoformat()

        # 현재 retry_count 가져오기
        current_retry = self.redis.hget(state_key, "retry_count")
        retry_count = int(current_retry) + 1 if current_retry else 1

        self.redis.hset(state_key, mapping={
            "status": JobStatus.FAILED,
            "error": error[:1000],  # 최대 1000자
            "retry_count": retry_count,
            "failed_at": now,
        })
        self.release_lock(job_id, job_type, worker_id)

        logger.warning(
            "job_failed",
            job_id=job_id,
            job_type=job_type,
            error=error[:200],
            retry_count=retry_count,
        )

    # ============================================================
    # 재시도 / 큐 관리
    # ============================================================

    def retry_job(self, job_id: str, job_type: str) -> bool:
        """작업 재시도 (failed 또는 stuck 상태에서)

        Returns:
            재시도 성공 여부 (max retries 초과 시 False)
        """
        state_key = self._state_key(job_type, job_id)
        queue_key = self._queue_key(job_type)

        state = self.redis.hgetall(state_key)
        if not state:
            logger.warning("retry_job_not_found", job_id=job_id)
            return False

        retry_count = int(state.get("retry_count", 0))
        if retry_count >= self.MAX_RETRIES:
            logger.warning(
                "retry_max_exceeded",
                job_id=job_id,
                retry_count=retry_count,
            )
            return False

        # 상태 업데이트 + 큐에 추가
        now = datetime.now(tz.utc).isoformat()
        pipe = self.redis.pipeline()
        pipe.hset(state_key, mapping={
            "status": JobStatus.QUEUED,
            "queued_at": now,
            "error": "",
            "worker_id": "",
        })
        pipe.rpush(queue_key, job_id)
        # 기존 락 제거
        pipe.delete(self._lock_key(job_type, job_id))
        pipe.execute()

        logger.info(
            "job_retried",
            job_id=job_id,
            job_type=job_type,
            retry_count=retry_count + 1,
        )
        return True

    def cancel_job(self, job_id: str, job_type: str) -> bool:
        """작업 취소

        Returns:
            취소 성공 여부
        """
        state_key = self._state_key(job_type, job_id)
        state = self.redis.hgetall(state_key)

        if not state:
            return False

        # 이미 완료된 작업은 취소 불가
        if state.get("status") == JobStatus.COMPLETED:
            return False

        now = datetime.now(tz.utc).isoformat()
        self.redis.hset(state_key, mapping={
            "status": JobStatus.CANCELLED,
            "cancelled_at": now,
        })
        self.force_release_lock(job_id, job_type)

        logger.info("job_cancelled", job_id=job_id, job_type=job_type)
        return True

    def pop_pending_job(self, job_type: str) -> Optional[str]:
        """대기 큐에서 작업 ID 꺼내기 (FIFO)

        Returns:
            작업 ID 또는 None
        """
        queue_key = self._queue_key(job_type)
        return self.redis.lpop(queue_key)

    def get_pending_count(self, job_type: str) -> int:
        """대기 큐의 작업 수"""
        queue_key = self._queue_key(job_type)
        return self.redis.llen(queue_key)

    # ============================================================
    # Stuck 작업 감지 및 복구
    # ============================================================

    def get_stuck_jobs(self, job_type: str, pattern: str = "*") -> list[str]:
        """Stuck 작업 감지 (heartbeat 타임아웃)

        Args:
            job_type: 작업 유형
            pattern: 검색 패턴

        Returns:
            stuck 상태인 작업 ID 리스트
        """
        stuck_jobs = []
        now = datetime.now(tz.utc)
        timeout_threshold = self.HEARTBEAT_TIMEOUT

        # job:{type}:*:state 패턴으로 검색
        state_pattern = f"job:{job_type}:{pattern}:state"

        for key in self.redis.scan_iter(match=state_pattern):
            state = self.redis.hgetall(key)

            if state.get("status") != JobStatus.PROCESSING:
                continue

            heartbeat_str = state.get("heartbeat", "")
            if not heartbeat_str:
                continue

            try:
                heartbeat = datetime.fromisoformat(heartbeat_str)
                elapsed = (now - heartbeat).total_seconds()

                if elapsed > timeout_threshold:
                    # key에서 job_id 추출: job:embed:xxx:state -> xxx
                    parts = key.split(":")
                    if len(parts) >= 3:
                        job_id = parts[2]
                        stuck_jobs.append(job_id)
                        logger.warning(
                            "stuck_job_detected",
                            job_id=job_id,
                            elapsed_seconds=elapsed,
                        )
            except (ValueError, TypeError):
                continue

        return stuck_jobs

    def recover_stuck_job(self, job_id: str, job_type: str) -> bool:
        """Stuck 작업 복구 (failed로 전환 후 재시도)

        Returns:
            복구 성공 여부
        """
        state_key = self._state_key(job_type, job_id)
        state = self.redis.hgetall(state_key)

        if not state or state.get("status") != JobStatus.PROCESSING:
            return False

        # 실패 처리
        self.redis.hset(state_key, mapping={
            "status": JobStatus.FAILED,
            "error": "Worker timeout (stuck recovery)",
            "failed_at": datetime.now(tz.utc).isoformat(),
        })
        self.force_release_lock(job_id, job_type)

        # 재시도 가능하면 재시도
        return self.retry_job(job_id, job_type)

    # ============================================================
    # DB 동기화
    # ============================================================

    def sync_from_db(
        self,
        job_id: str,
        job_type: str,
        db_status: str,
        db_data: dict,
    ) -> None:
        """DB 상태를 Redis로 동기화 (서버 시작 시 또는 Redis 장애 복구 시)

        Args:
            job_id: 작업 ID
            job_type: 작업 유형
            db_status: DB의 상태
            db_data: DB의 추가 데이터
        """
        state_key = self._state_key(job_type, job_id)

        # Redis에 이미 있으면 스킵
        if self.redis.exists(state_key):
            return

        # DB 상태를 Redis 상태로 매핑
        status_map = {
            "pending": JobStatus.QUEUED,  # pending은 queued로 간주
            "processing": JobStatus.PROCESSING,
            "completed": JobStatus.COMPLETED,
            "failed": JobStatus.FAILED,
        }
        redis_status = status_map.get(db_status, db_status)

        state = {
            "status": redis_status,
            "progress": db_data.get("paper_count", 0),
            "total": db_data.get("total", 0),
            "retry_count": db_data.get("retry_count", 0),
            "error": db_data.get("error_message", "") or "",
            "created_at": db_data.get("created_at", ""),
            "synced_from_db": "true",
        }

        self.redis.hset(state_key, mapping=state)

        # pending/queued 상태면 큐에도 추가
        if redis_status == JobStatus.QUEUED:
            queue_key = self._queue_key(job_type)
            self.redis.rpush(queue_key, job_id)

        logger.info(
            "job_synced_from_db",
            job_id=job_id,
            job_type=job_type,
            status=redis_status,
        )

    def delete_job(self, job_id: str, job_type: str) -> None:
        """작업 상태 삭제 (Redis에서)"""
        state_key = self._state_key(job_type, job_id)
        lock_key = self._lock_key(job_type, job_id)

        self.redis.delete(state_key, lock_key)
        logger.debug("job_deleted_from_redis", job_id=job_id, job_type=job_type)


# 싱글톤 인스턴스
_job_manager: Optional[JobStateManager] = None


def get_job_manager() -> JobStateManager:
    """JobStateManager 싱글톤 인스턴스 반환"""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobStateManager()
    return _job_manager
