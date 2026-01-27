"""Agent Job Executor

에이전트 작업의 백그라운드 실행을 담당.
- 작업 타입에 따른 서비스 호출
- SSE를 통한 진행 상태 스트리밍
- DB 상태 업데이트
- 승인 워크플로우 처리
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.sse_manager import sse_manager
from ..database import async_session_maker
from ..models.agent_job import AgentJob, AgentJobStatus
from ..services.agent.study_plan.v4.service import get_study_plan_agent_v4
from ..services.agent.study_plan.v4.langgraph.routing import AgentLoopEvent
from .agent_job_service import AgentJobService
from .notification_service import NotificationService

logger = logging.getLogger(__name__)




class AgentJobExecutor:
    """에이전트 작업 실행기"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.job_service = AgentJobService(db)
        self.notification_service = NotificationService(db)
        # Thinking history 수집용
        self._thinking_history: list[dict[str, Any]] = []
        self._cumulative_tokens: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    async def execute(self, job_id: UUID) -> None:
        """작업 실행

        Args:
            job_id: 실행할 작업 ID
        """
        logger.info(f"[JobExecutor] Starting execution for job {job_id}")

        # 작업 조회
        job = await self.job_service.get_by_id(job_id)
        if not job:
            logger.error(f"[JobExecutor] Job {job_id} not found")
            return

        # 상태 확인
        if job.status not in [AgentJobStatus.QUEUED.value, AgentJobStatus.APPROVED.value]:
            logger.warning(
                f"[JobExecutor] Job {job_id} is not in executable state: {job.status}"
            )
            return

        try:
            # 작업 타입에 따라 분기
            if job.agent_type.startswith("study_plan"):
                await self._execute_study_plan(job)
            else:
                raise ValueError(f"Unknown agent type: {job.agent_type}")

        except Exception as e:
            logger.error(f"[JobExecutor] Job {job_id} failed: {e}")
            await self._handle_failure(job, error=str(e))

    async def _execute_study_plan(self, job: AgentJob) -> None:
        """Study Plan 에이전트 실행 (v4 ReAct only)"""
        job_id = job.id
        user_id = job.user_id
        input_data = job.input_data or {}

        # Reset thinking history for new execution
        self._thinking_history = []
        self._cumulative_tokens = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        logger.info(f"[JobExecutor] Executing Study Plan v4 for job {job_id}")

        # 작업 시작
        job = await self.job_service.start_job(job)

        # SSE로 시작 이벤트 전송
        await sse_manager.send_to_job_subscribers(
            job_id=job_id,
            event_type="status",
            data={
                "job_id": str(job_id),
                "status": job.status,
                "progress_percent": 0,
                "current_step": "starting",
                "message": "연구 계획 생성을 시작합니다",
            },
        )

        # 입력 데이터 추출
        hypothesis = input_data.get("hypothesis", "")
        research_context = input_data.get("research_context")
        constraints = input_data.get("constraints", [])
        preferred_experiment_types = input_data.get("preferred_experiment_types", [])

        try:
            # v4 ReAct 스트리밍 실행 (only v4 supported)
            agent_v4 = get_study_plan_agent_v4()
            async for event_type, event_data in agent_v4.execute_stream(
                hypothesis=hypothesis,
                research_context=research_context,
                constraints=constraints,
                preferred_experiment_types=preferred_experiment_types,
                user_id=str(user_id),
            ):
                await self._process_v4_event(job, event_type, event_data)

        except Exception as e:
            logger.error(f"[JobExecutor] Study Plan execution error: {e}")
            raise

    async def _process_v4_event(
        self, job: AgentJob, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """v4 ReAct 에이전트 이벤트 처리

        Args:
            job: 작업 객체
            event_type: AgentLoopEvent 타입 (문자열)
            event_data: 이벤트 데이터
        """
        job_id = job.id

        # 진행률 계산
        iteration = event_data.get("iteration", 0)
        max_iter = 30  # default max_iterations
        progress = min(95, int((iteration / max_iter) * 95))

        # 이벤트 타입에 따른 처리
        if event_type == AgentLoopEvent.STARTED:
            await self.job_service.update_progress(
                job=job,
                current_step="started",
                progress_percent=5,
                progress_detail="ReAct 에이전트 시작",
            )
            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="status",
                data={
                    "job_id": str(job_id),
                    "event": "started",
                    "progress_percent": 5,
                    "message": "ReAct 에이전트가 시작되었습니다",
                    **event_data,
                },
            )

        elif event_type == AgentLoopEvent.THINKING:
            # Collect thinking event for history
            thinking_entry = {
                "iteration": iteration,
                "timestamp": event_data.get("timestamp"),
                "title": event_data.get("title", f"Iteration {iteration}"),
                "bullets": event_data.get("bullets", []),
                "message": event_data.get("message", ""),
                "confidence": event_data.get("confidence", 0),
                "status": "completed",
            }

            # Track token usage
            if event_data.get("token_usage"):
                token_usage = event_data["token_usage"]
                thinking_entry["token_usage"] = token_usage
                self._cumulative_tokens["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
                self._cumulative_tokens["completion_tokens"] += token_usage.get("completion_tokens", 0)
                self._cumulative_tokens["total_tokens"] += token_usage.get("total_tokens", 0)

            self._thinking_history.append(thinking_entry)

            await self.job_service.update_progress(
                job=job,
                current_step="thinking",
                progress_percent=progress,
                progress_detail=f"Iteration {iteration}: 다음 행동 결정 중...",
            )

            # 매 5번째 iteration마다 thinking_history를 DB에 저장 (중간 저장)
            if iteration % 5 == 0:
                await self.job_service.save_thinking_history(
                    job=job,
                    thinking_history=self._thinking_history,
                    cumulative_tokens=self._cumulative_tokens,
                )

            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="thinking",
                data={
                    "job_id": str(job_id),
                    "event": "thinking",
                    "progress_percent": progress,
                    "iteration": iteration,
                    **event_data,
                },
            )

        elif event_type == AgentLoopEvent.ACTING:
            action = event_data.get("action", "unknown")

            # Update the last thinking entry with the action taken
            if self._thinking_history:
                self._thinking_history[-1]["action"] = action
                self._thinking_history[-1]["parameters"] = event_data.get("parameters", {})

            await self.job_service.update_progress(
                job=job,
                current_step=f"action:{action}",
                progress_percent=progress,
                progress_detail=f"도구 실행: {action}",
            )
            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="acting",
                data={
                    "job_id": str(job_id),
                    "event": "acting",
                    "progress_percent": progress,
                    "action": action,
                    **event_data,
                },
            )

        elif event_type == AgentLoopEvent.OBSERVATION:
            action = event_data.get("action", "unknown")
            success = event_data.get("success", False)

            # Update the last thinking entry with observation result
            if self._thinking_history:
                self._thinking_history[-1]["observation"] = {
                    "success": success,
                    "summary": event_data.get("summary", ""),
                    "details": event_data.get("details"),
                }

            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="observation",
                data={
                    "job_id": str(job_id),
                    "event": "observation",
                    "progress_percent": progress,
                    "action": action,
                    "success": success,
                    **event_data,
                },
            )

        elif event_type == AgentLoopEvent.RECOVERY:
            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="recovery",
                data={
                    "job_id": str(job_id),
                    "event": "recovery",
                    "progress_percent": progress,
                    **event_data,
                },
            )

        elif event_type == AgentLoopEvent.GOAL_CHECK:
            achieved = event_data.get("achieved", False)
            if achieved:
                await self.job_service.update_progress(
                    job=job,
                    current_step="goal_achieved",
                    progress_percent=95,
                    progress_detail="목표 달성됨",
                )

        elif event_type == AgentLoopEvent.COMPLETED:
            # 완료 처리
            result_data = {
                "plan_a": event_data.get("plan_a", ""),
                "plan_b": event_data.get("plan_b", ""),
                "executive_summary": event_data.get("executive_summary", ""),
                "quality_score": event_data.get("quality_score", 0),
                "success": event_data.get("success", True),
            }

            experiment_count = event_data.get("experiment_count", 0)

            # Save final thinking history before completing
            await self.job_service.save_thinking_history(
                job=job,
                thinking_history=self._thinking_history,
                cumulative_tokens=self._cumulative_tokens,
            )

            job = await self.job_service.complete(
                job=job,
                result_data=result_data,
                executive_summary=result_data.get("executive_summary", ""),
                experiment_count=experiment_count,
            )

            # 알림 생성
            notification = await self.notification_service.notify_job_completed(job)

            # SSE로 완료 이벤트 전송
            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="completed",
                data={
                    "job_id": str(job_id),
                    "event": "completed",
                    "success": True,
                    "status": job.status,
                    "progress_percent": 100,
                    "experiment_count": experiment_count,
                    **result_data,
                },
            )

            # 알림 브로드캐스트
            await sse_manager.broadcast_notification(
                user_id=job.user_id,
                notification_data={
                    "id": str(notification.id),
                    "type": notification.type,
                    "title": notification.title,
                    "message": notification.message,
                    "entity_id": str(job_id),
                },
            )

            logger.info(f"[JobExecutor] v4 Job {job_id} completed")

        elif event_type == AgentLoopEvent.ERROR:
            error = event_data.get("error", "Unknown error")
            is_critical = event_data.get("critical", False)

            logger.error(f"[JobExecutor] v4 error (critical={is_critical}): {error}")
            await self._handle_failure(job, error=error)

    async def _handle_failure(self, job: AgentJob, error: str) -> None:
        """실패 처리"""
        job_id = job.id
        user_id = job.user_id

        # 실패 상태로 업데이트
        job = await self.job_service.fail(
            job=job,
            error_code="EXECUTION_ERROR",
            error_message=error,
        )

        # 알림 생성
        notification = await self.notification_service.notify_job_failed(job)

        # SSE로 실패 이벤트 전송
        await sse_manager.send_to_job_subscribers(
            job_id=job_id,
            event_type="failed",
            data={
                "job_id": str(job_id),
                "event": "failed",
                "error": error,
                "status": job.status,
            },
        )

        # 알림 브로드캐스트
        await sse_manager.broadcast_notification(
            user_id=user_id,
            notification_data={
                "id": str(notification.id),
                "type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "entity_id": str(job_id),
            },
        )

        logger.error(f"[JobExecutor] Job {job_id} failed: {error}")


# ============================================================
# 백그라운드 실행 함수
# ============================================================


async def execute_job_background(job_id: UUID) -> None:
    """백그라운드에서 작업 실행

    새로운 DB 세션을 생성하여 작업을 실행합니다.
    FastAPI의 BackgroundTasks에서 호출됩니다.
    """
    logger.info(f"[Background] Starting job execution: {job_id}")

    async with async_session_maker() as db:
        executor = AgentJobExecutor(db)
        try:
            await executor.execute(job_id)
        except Exception as e:
            logger.error(f"[Background] Job {job_id} execution failed: {e}")
            # 실패 처리는 executor 내부에서 이미 수행됨


def schedule_job_execution(job_id: UUID) -> asyncio.Task:
    """작업 실행 스케줄링

    asyncio.create_task를 사용하여 백그라운드에서 실행.

    Args:
        job_id: 실행할 작업 ID

    Returns:
        생성된 태스크
    """
    task = asyncio.create_task(execute_job_background(job_id))
    logger.info(f"[Scheduler] Scheduled job execution: {job_id}")
    return task
