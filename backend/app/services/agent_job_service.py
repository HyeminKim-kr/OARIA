"""Agent Job 서비스

백그라운드 에이전트 작업의 생명주기 관리.
- 작업 생성, 조회, 상태 업데이트
- 승인 워크플로우 처리
- 재시도 로직
"""

import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent_job import AgentJob, AgentJobStatus
from ..schemas.agent_job import (
    AgentJobCreateRequest,
    AgentJobListItem,
    PaginatedAgentJobs,
)


class AgentJobService:
    """Agent Job CRUD 및 상태 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # CRUD 메서드
    # ============================================================

    async def create(
        self,
        user_id: UUID,
        request: AgentJobCreateRequest,
    ) -> AgentJob:
        """새 에이전트 작업 생성"""
        # 작업 이름 생성 (지정되지 않은 경우)
        job_name = request.job_name
        if not job_name:
            # 입력에서 가설 추출하여 사용
            hypothesis = request.input_data.get("hypothesis", "")
            job_name = hypothesis[:100] if hypothesis else f"{request.agent_type} job"

        job = AgentJob(
            user_id=user_id,
            agent_type=request.agent_type,
            job_name=job_name,
            input_data=request.input_data,
            config=request.config,
            status=AgentJobStatus.PENDING.value,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> AgentJob | None:
        """ID로 작업 조회"""
        result = await self.db.execute(
            select(AgentJob).where(
                and_(
                    AgentJob.id == job_id,
                    AgentJob.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, job_id: UUID, user_id: UUID) -> AgentJob | None:
        """사용자 소유 작업 조회"""
        result = await self.db.execute(
            select(AgentJob).where(
                and_(
                    AgentJob.id == job_id,
                    AgentJob.user_id == user_id,
                    AgentJob.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        user_id: UUID,
        page: int = 1,
        size: int = 10,
        status_filter: list[str] | None = None,
        agent_type_filter: str | None = None,
    ) -> PaginatedAgentJobs:
        """사용자 작업 목록 조회"""
        # 기본 필터
        conditions = [
            AgentJob.user_id == user_id,
            AgentJob.deleted_at.is_(None),
        ]

        # 상태 필터
        if status_filter:
            conditions.append(AgentJob.status.in_(status_filter))

        # 에이전트 유형 필터
        if agent_type_filter:
            conditions.append(AgentJob.agent_type == agent_type_filter)

        # 전체 개수 조회
        count_query = select(func.count()).select_from(AgentJob).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar() or 0

        # 페이지네이션 계산
        pages = math.ceil(total / size) if total > 0 else 1
        offset = (page - 1) * size

        # 데이터 조회
        query = (
            select(AgentJob)
            .where(and_(*conditions))
            .order_by(AgentJob.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        result = await self.db.execute(query)
        jobs = result.scalars().all()

        # 응답 변환
        items = [
            AgentJobListItem(
                id=job.id,
                agent_type=job.agent_type,
                job_name=job.job_name,
                status=job.status,
                progress_percent=job.progress_percent,
                approval_required=job.approval_required,
                experiment_count=job.experiment_count,
                created_at=job.created_at,
            )
            for job in jobs
        ]

        return PaginatedAgentJobs(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def get_waiting_approval(self, user_id: UUID) -> list[AgentJob]:
        """승인 대기 중인 작업 목록"""
        result = await self.db.execute(
            select(AgentJob).where(
                and_(
                    AgentJob.user_id == user_id,
                    AgentJob.status == AgentJobStatus.WAITING_APPROVAL.value,
                    AgentJob.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())

    async def get_running_jobs(self, user_id: UUID) -> list[AgentJob]:
        """실행 중인 작업 목록"""
        result = await self.db.execute(
            select(AgentJob).where(
                and_(
                    AgentJob.user_id == user_id,
                    AgentJob.status.in_([
                        AgentJobStatus.QUEUED.value,
                        AgentJobStatus.RUNNING.value,
                        AgentJobStatus.APPROVED.value,
                    ]),
                    AgentJob.deleted_at.is_(None),
                )
            )
        )
        return list(result.scalars().all())

    # ============================================================
    # 상태 변경 메서드
    # ============================================================

    async def start_job(self, job: AgentJob) -> AgentJob:
        """작업 시작 (QUEUED → RUNNING)"""
        job.status = AgentJobStatus.RUNNING.value
        job.started_at = datetime.now(timezone.utc)
        job.attempt_count += 1
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def update_progress(
        self,
        job: AgentJob,
        current_step: str,
        progress_percent: int,
        progress_detail: str | None = None,
        step_result: dict[str, Any] | None = None,
    ) -> AgentJob:
        """진행 상태 업데이트"""
        job.current_step = current_step
        job.progress_percent = min(100, max(0, progress_percent))
        if progress_detail:
            job.progress_detail = progress_detail

        if step_result:
            current_results = job.step_results or []
            current_results.append({
                "step": current_step,
                "result": step_result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            job.step_results = current_results

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def save_thinking_history(
        self,
        job: AgentJob,
        thinking_history: list[dict[str, Any]],
        cumulative_tokens: dict[str, int] | None = None,
    ) -> AgentJob:
        """Thinking history 저장 (에이전트 reasoning 과정)

        페이지 새로고침 시에도 복원 가능하도록 DB에 저장합니다.

        Args:
            job: 작업 객체
            thinking_history: thinking 이벤트 리스트
            cumulative_tokens: 누적 토큰 사용량
        """
        job.thinking_history = thinking_history
        if cumulative_tokens:
            job.cumulative_tokens = cumulative_tokens
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def set_waiting_approval(
        self,
        job: AgentJob,
        gate_id: str,
        choices: dict[str, Any],
    ) -> AgentJob:
        """승인 대기 상태로 전환"""
        job.status = AgentJobStatus.WAITING_APPROVAL.value
        job.approval_required = True
        job.approval_gate_id = gate_id
        job.approval_choices = choices
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def approve(
        self,
        job: AgentJob,
        decision: dict[str, Any],
    ) -> AgentJob:
        """승인 처리 (WAITING_APPROVAL → APPROVED)"""
        job.status = AgentJobStatus.APPROVED.value
        job.approval_decision = decision
        job.approved_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def complete(
        self,
        job: AgentJob,
        result_data: dict[str, Any],
        executive_summary: str | None = None,
        experiment_count: int = 0,
    ) -> AgentJob:
        """작업 완료 처리"""
        job.status = AgentJobStatus.COMPLETED.value
        job.result_data = result_data
        job.executive_summary = executive_summary
        job.experiment_count = experiment_count
        job.progress_percent = 100
        job.completed_at = datetime.now(timezone.utc)

        # 전체 소요 시간 계산
        if job.started_at:
            duration = job.completed_at - job.started_at
            job.total_duration_ms = int(duration.total_seconds() * 1000)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def fail(
        self,
        job: AgentJob,
        error_code: str,
        error_message: str,
    ) -> AgentJob:
        """작업 실패 처리"""
        job.status = AgentJobStatus.FAILED.value
        job.last_error_code = error_code
        job.last_error_message = error_message
        job.completed_at = datetime.now(timezone.utc)

        if job.started_at:
            duration = job.completed_at - job.started_at
            job.total_duration_ms = int(duration.total_seconds() * 1000)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def cancel(self, job: AgentJob) -> AgentJob:
        """작업 취소"""
        job.status = AgentJobStatus.CANCELLED.value
        job.completed_at = datetime.now(timezone.utc)

        if job.started_at:
            duration = job.completed_at - job.started_at
            job.total_duration_ms = int(duration.total_seconds() * 1000)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def retry(
        self,
        job: AgentJob,
        reset_config: dict[str, Any] | None = None,
    ) -> AgentJob:
        """실패 작업 재시도"""
        if not job.can_retry:
            raise ValueError("작업을 재시도할 수 없습니다")

        # 상태 초기화
        job.status = AgentJobStatus.QUEUED.value
        job.current_step = None
        job.progress_percent = 0
        job.progress_detail = None
        job.last_error_code = None
        job.last_error_message = None
        job.started_at = None
        job.completed_at = None
        job.total_duration_ms = None

        # 설정 업데이트 (선택적)
        if reset_config:
            current_config = job.config or {}
            current_config.update(reset_config)
            job.config = current_config

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def soft_delete(self, job: AgentJob) -> AgentJob:
        """작업 소프트 삭제"""
        job.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    # ============================================================
    # 유틸리티 메서드
    # ============================================================

    async def queue_job(self, job: AgentJob) -> AgentJob:
        """작업을 큐에 추가 (PENDING → QUEUED)"""
        job.status = AgentJobStatus.QUEUED.value
        await self.db.commit()
        await self.db.refresh(job)
        return job
