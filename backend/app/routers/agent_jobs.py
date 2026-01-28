"""Agent Jobs 라우터

백그라운드 에이전트 작업 관리 엔드포인트.
- 작업 생성, 조회, 취소
- 승인 워크플로우
- SSE 스트리밍
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.sse_manager import sse_manager
from app.database import get_db
from app.dependencies import CurrentUser
from app.models.agent_job import AgentJobStatus
from app.schemas.agent_job import (
    AgentJobApprovalRequest,
    AgentJobCreateRequest,
    AgentJobDetailResponse,
    AgentJobResponse,
    AgentJobRetryRequest,
    PaginatedAgentJobs,
)
from app.schemas.notification import NotificationCreateInternal
from app.services.agent_job_service import AgentJobService
from app.services.agent_job_executor import schedule_job_execution
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-jobs", tags=["agent-jobs"])


# ─────────────────────────────────────────────────────────────
# Create Job
# ─────────────────────────────────────────────────────────────


@router.post("/", response_model=AgentJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: AgentJobCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """새 에이전트 작업 생성

    작업을 생성하고 큐에 추가합니다.
    작업 실행은 백그라운드에서 진행되며,
    /agent-jobs/{id}/stream으로 진행 상태를 확인할 수 있습니다.

    Returns:
        생성된 작업 정보
    """
    logger.info(f"Creating agent job for user {current_user.id}: {request.agent_type}")

    job_service = AgentJobService(db)
    notification_service = NotificationService(db)

    try:
        # 작업 생성
        job = await job_service.create(user_id=current_user.id, request=request)

        # 큐에 추가
        job = await job_service.queue_job(job)

        # 시작 알림 생성
        notification = await notification_service.notify_job_started(job)

        # SSE로 알림 브로드캐스트
        await sse_manager.broadcast_notification(
            user_id=current_user.id,
            notification_data={
                "id": str(notification.id),
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "entity_id": str(job.id),
            },
        )

        # 백그라운드에서 작업 실행 시작
        schedule_job_execution(job.id)

        logger.info(f"Agent job created and scheduled: {job.id}")
        return job

    except Exception as e:
        logger.error(f"Error creating agent job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"작업 생성 실패: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# List Jobs
# ─────────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedAgentJobs)
async def list_jobs(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    size: int = 10,
    status_filter: str | None = None,
    agent_type: str | None = None,
):
    """사용자 작업 목록 조회

    Args:
        page: 페이지 번호 (1부터 시작)
        size: 페이지당 항목 수 (기본 10, 최대 50)
        status_filter: 상태 필터 (쉼표로 구분, 예: "running,waiting_approval")
        agent_type: 에이전트 유형 필터
    """
    if size > 50:
        size = 50
    if page < 1:
        page = 1

    # 상태 필터 파싱
    status_list = None
    if status_filter:
        status_list = [s.strip() for s in status_filter.split(",")]

    job_service = AgentJobService(db)
    return await job_service.get_list(
        user_id=current_user.id,
        page=page,
        size=size,
        status_filter=status_list,
        agent_type_filter=agent_type,
    )


# ─────────────────────────────────────────────────────────────
# Get Job Detail
# ─────────────────────────────────────────────────────────────


@router.get("/{job_id}", response_model=AgentJobDetailResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """작업 상세 조회"""
    job_service = AgentJobService(db)
    job = await job_service.get_by_id_for_user(job_id=job_id, user_id=current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다.",
        )

    return job


# ─────────────────────────────────────────────────────────────
# Job Stream (SSE)
# ─────────────────────────────────────────────────────────────


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """작업 진행 상태 SSE 스트리밍

    작업의 실시간 진행 상태를 스트리밍합니다.
    작업이 완료되거나 실패하면 스트림이 종료됩니다.

    **SSE 이벤트 타입:**
    - `status`: 상태 변경
    - `progress`: 진행률 업데이트
    - `step_complete`: 단계 완료
    - `approval_required`: 승인 대기
    - `completed`: 작업 완료
    - `failed`: 작업 실패
    - `heartbeat`: 연결 유지
    """
    job_service = AgentJobService(db)
    job = await job_service.get_by_id_for_user(job_id=job_id, user_id=current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다.",
        )

    # 이미 완료된 작업인 경우 즉시 결과 반환
    if job.is_terminal:
        async def immediate_response():
            if job.status == AgentJobStatus.COMPLETED.value:
                yield {
                    "event": "completed",
                    "data": json.dumps({
                        "job_id": str(job.id),
                        "status": job.status,
                        "result_data": job.result_data,
                        "experiment_count": job.experiment_count,
                    }, ensure_ascii=False),
                }
            else:
                yield {
                    "event": "failed" if job.status == AgentJobStatus.FAILED.value else "cancelled",
                    "data": json.dumps({
                        "job_id": str(job.id),
                        "status": job.status,
                        "error_code": job.last_error_code,
                        "error_message": job.last_error_message,
                    }, ensure_ascii=False),
                }

        return EventSourceResponse(immediate_response())

    # SSE 연결 등록
    connection_id = f"{current_user.id}-{job_id}-{uuid.uuid4().hex[:8]}"
    connection = await sse_manager.connect(current_user.id, connection_id)
    await sse_manager.subscribe_job(current_user.id, connection_id, job_id)

    async def generate_events():
        try:
            # 초기 상태 전송
            yield {
                "event": "status",
                "data": json.dumps({
                    "job_id": str(job.id),
                    "status": job.status,
                    "progress_percent": job.progress_percent,
                    "current_step": job.current_step,
                }, ensure_ascii=False),
            }

            # 스트림 이벤트
            async for event_str in sse_manager.stream_events(connection):
                yield event_str

        finally:
            await sse_manager.disconnect(current_user.id, connection_id)

    return EventSourceResponse(generate_events())


# ─────────────────────────────────────────────────────────────
# Approve Job
# ─────────────────────────────────────────────────────────────


@router.post("/{job_id}/approve", response_model=AgentJobResponse)
async def approve_job(
    job_id: uuid.UUID,
    request: AgentJobApprovalRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """작업 승인 제출

    승인 대기 중인 작업에 대한 결정을 제출합니다.
    승인 후 작업이 다음 단계로 진행됩니다.
    """
    job_service = AgentJobService(db)
    notification_service = NotificationService(db)

    job = await job_service.get_by_id_for_user(job_id=job_id, user_id=current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다.",
        )

    if job.status != AgentJobStatus.WAITING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="승인 대기 상태가 아닙니다.",
        )

    try:
        # 승인 처리
        job = await job_service.approve(job=job, decision=request.decision)

        # 승인 알림
        notification = await notification_service.create(
            data=NotificationCreateInternal(
                user_id=current_user.id,
                type="job_approved",
                category="agent",
                title="작업이 승인되었습니다",
                message=f"{job.job_name or job.agent_type} 작업이 승인되어 다음 단계로 진행됩니다.",
                entity_type="agent_job",
                entity_id=job.id,
            )
        )

        # SSE로 알림 브로드캐스트
        await sse_manager.broadcast_notification(
            user_id=current_user.id,
            notification_data={
                "id": str(notification.id),
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "entity_id": str(job.id),
            },
        )

        # 승인 후 작업 재개
        schedule_job_execution(job.id)

        logger.info(f"Job {job_id} approved and resumed by user {current_user.id}")
        return job

    except Exception as e:
        logger.error(f"Error approving job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"승인 처리 실패: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# Cancel Job
# ─────────────────────────────────────────────────────────────


@router.post("/{job_id}/cancel", response_model=AgentJobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """작업 취소

    실행 중이거나 대기 중인 작업을 취소합니다.
    이미 완료된 작업은 취소할 수 없습니다.
    """
    job_service = AgentJobService(db)
    job = await job_service.get_by_id_for_user(job_id=job_id, user_id=current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다.",
        )

    if job.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 종료된 작업입니다.",
        )

    try:
        job = await job_service.cancel(job)

        # 작업 구독자들에게 취소 알림
        await sse_manager.send_to_job_subscribers(
            job_id=job_id,
            event_type="cancelled",
            data={
                "job_id": str(job.id),
                "status": job.status,
            },
        )

        logger.info(f"Job {job_id} cancelled by user {current_user.id}")
        return job

    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"취소 처리 실패: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# Retry Job
# ─────────────────────────────────────────────────────────────


@router.post("/{job_id}/retry", response_model=AgentJobResponse)
async def retry_job(
    job_id: uuid.UUID,
    request: AgentJobRetryRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """실패 작업 재시도

    실패한 작업을 재시도합니다.
    최대 재시도 횟수를 초과한 경우 재시도할 수 없습니다.
    """
    job_service = AgentJobService(db)
    job = await job_service.get_by_id_for_user(job_id=job_id, user_id=current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다.",
        )

    if not job.can_retry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"재시도할 수 없습니다 (시도: {job.attempt_count}/{job.max_attempts}).",
        )

    try:
        job = await job_service.retry(job=job, reset_config=request.reset_config)

        # 재시도 후 작업 재실행
        schedule_job_execution(job.id)

        logger.info(f"Job {job_id} retried and rescheduled by user {current_user.id}")
        return job

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"재시도 처리 실패: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# Delete Job
# ─────────────────────────────────────────────────────────────


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """작업 삭제 (소프트 삭제)

    작업을 삭제합니다. 실제 데이터는 유지되며 deleted_at 필드가 설정됩니다.
    """
    job_service = AgentJobService(db)
    job = await job_service.get_by_id_for_user(job_id=job_id, user_id=current_user.id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="작업을 찾을 수 없습니다.",
        )

    try:
        await job_service.soft_delete(job)
        logger.info(f"Job {job_id} deleted by user {current_user.id}")

    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"삭제 처리 실패: {str(e)}",
        )
