"""Agent Job Executor

에이전트 작업의 백그라운드 실행을 담당.
- 작업 타입에 따른 서비스 호출
- SSE를 통한 진행 상태 스트리밍
- DB 상태 업데이트
- 승인 워크플로우 처리
"""

import asyncio
import logging
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.sse_manager import sse_manager
from ..database import async_session_maker
from ..models.agent_job import AgentJob, AgentJobStatus
from ..schemas.notification import NotificationCreateInternal
from ..services.agent.study_plan.service import (
    StudyPlanEventType,
    study_plan_service,
)
from ..services.agent.study_plan.nodes.synthesize_plan_v3 import synthesize_plan_v3
from ..services.agent.study_plan.v4.service import get_study_plan_agent_v4
from ..services.agent.study_plan.v4.core.loop import AgentLoopEvent
from ..services.agent.study_plan.state import (
    ApprovalStatus,
    create_initial_state,
    ExperimentType,
)
from .agent_job_service import AgentJobService
from .notification_service import NotificationService

logger = logging.getLogger(__name__)


# 노드 → 진행률 매핑 (v3)
NODE_PROGRESS_MAP = {
    "parse_hypothesis": 10,
    "clarify_hypothesis": 15,
    "decompose_tests": 25,
    "search_v3": 40,
    "search_controls": 50,
    "build_evidence": 60,
    "analyze_methodologies": 65,
    "design_experiments": 75,
    "critique_v3": 82,
    "identify_measurements": 87,
    "validate_feasibility": 92,
    "approval_gate": 95,
    "synthesize_v3": 100,
    "synthesize_plan": 100,
}


class AgentJobExecutor:
    """에이전트 작업 실행기"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.job_service = AgentJobService(db)
        self.notification_service = NotificationService(db)

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
        """Study Plan 에이전트 실행"""
        job_id = job.id
        user_id = job.user_id
        input_data = job.input_data or {}
        is_resume = job.status == AgentJobStatus.APPROVED.value

        logger.info(
            f"[JobExecutor] {'Resuming' if is_resume else 'Executing'} "
            f"Study Plan for job {job_id}"
        )

        # 승인 후 재개인 경우 별도 처리
        if is_resume:
            await self._resume_after_approval(job)
            return

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
        conversation_id = input_data.get("conversation_id")

        # 버전 확인 (v3 or v4)
        is_v3 = job.agent_type in ["study_plan_v3", "study_plan"]

        try:
            if is_v3:
                # v3 스트리밍 실행
                async for event in study_plan_service.execute_stream_v3(
                    user_input=hypothesis,
                    research_context=research_context,
                    constraints=constraints,
                    preferred_experiment_types=preferred_experiment_types,
                    conversation_id=conversation_id,
                    user_id=str(user_id),
                ):
                    await self._process_event(job, event)
            else:
                # v4 ReAct 스트리밍 실행
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

    async def _resume_after_approval(self, job: AgentJob) -> None:
        """승인 후 재개: 저장된 상태에서 synthesize만 실행"""
        job_id = job.id
        user_id = job.user_id
        input_data = job.input_data or {}
        step_results = job.step_results or []
        approval_decision = job.approval_decision or {}

        logger.info(f"[JobExecutor] Resuming job {job_id} after approval")

        # 상태를 RUNNING으로 변경
        job.status = AgentJobStatus.RUNNING.value
        job.current_step = "synthesizing"
        job.progress_percent = 95
        await self.db.commit()
        await self.db.refresh(job)

        # SSE로 재개 이벤트 전송
        await sse_manager.send_to_job_subscribers(
            job_id=job_id,
            event_type="status",
            data={
                "job_id": str(job_id),
                "status": job.status,
                "progress_percent": 95,
                "current_step": "synthesizing",
                "message": "승인이 완료되었습니다. 최종 계획서를 작성합니다.",
            },
        )

        try:
            # step_results에서 상태 재구성
            state = self._reconstruct_state_from_results(
                input_data=input_data,
                step_results=step_results,
                approval_decision=approval_decision,
                user_id=str(user_id),
            )

            # synthesize_plan_v3 직접 호출
            synthesis_result = await synthesize_plan_v3(state)

            # 결과 병합
            final_state = {**state, **synthesis_result}

            # 완료 처리
            result_data = {
                "final_plan": final_state.get("final_plan", ""),
                "executive_summary": final_state.get("executive_summary", ""),
                "plan_a": final_state.get("plan_a", ""),
                "plan_b": final_state.get("plan_b", ""),
                "dp3_decision": final_state.get("dp3_decision", "single_plan"),
                "highest_tier_used": final_state.get("current_tier", 1),
                "success": True,
            }

            experiment_count = len(final_state.get("experiment_designs", []))

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
                user_id=user_id,
                notification_data={
                    "id": str(notification.id),
                    "type": notification.type,
                    "title": notification.title,
                    "message": notification.message,
                    "entity_id": str(job_id),
                },
            )

            logger.info(f"[JobExecutor] Job {job_id} resumed and completed")

        except Exception as e:
            logger.error(f"[JobExecutor] Resume failed for job {job_id}: {e}")
            await self._handle_failure(job, error=str(e))

    def _reconstruct_state_from_results(
        self,
        input_data: dict[str, Any],
        step_results: list[dict[str, Any]],
        approval_decision: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """step_results에서 StudyPlanState 재구성"""
        # 기본 상태 생성
        hypothesis = input_data.get("hypothesis", "")
        research_context = input_data.get("research_context")
        constraints = input_data.get("constraints", [])
        preferred_exp_types = input_data.get("preferred_experiment_types", [])

        # 실험 유형 변환
        exp_types = []
        for t in preferred_exp_types:
            try:
                exp_types.append(ExperimentType(t))
            except ValueError:
                pass

        state = create_initial_state(
            user_input=hypothesis,
            research_context=research_context,
            constraints=constraints,
            preferred_experiment_types=exp_types,
            user_id=user_id,
        )

        # step_results에서 상태 복원
        for step_entry in step_results:
            step_data = step_entry.get("result", {})
            step_name = step_entry.get("step", "")

            # 각 단계별 데이터 병합
            if step_name == "parse_hypothesis":
                if "hypothesis" in step_data:
                    state["hypothesis"] = step_data["hypothesis"]
                if "confidence" in step_data:
                    state["hypothesis_confidence"] = step_data["confidence"]

            elif step_name in ("search_v3", "search_studies"):
                if "study_count" in step_data:
                    # prior_studies는 step_data에 직접 포함되지 않음
                    # 대신 coverage와 tier 정보만 저장
                    state["search_coverage_score"] = step_data.get("coverage", 0)
                    state["current_tier"] = step_data.get("current_tier", 1)

            elif step_name == "decompose_tests":
                if "test_questions" in step_data:
                    state["test_questions"] = step_data["test_questions"]

            elif step_name == "design_experiments":
                if "experiments" in step_data:
                    state["experiment_designs"] = step_data["experiments"]

            elif step_name in ("critique_v3", "critique_refine"):
                if "quality_score" in step_data:
                    state["critique_result"] = {
                        "quality_score": step_data.get("quality_score", 0),
                        "passed": step_data.get("passed", True),
                        "suggestions": step_data.get("suggestions", []),
                    }
                if "dp2_decision" in step_data:
                    state["dp2_decision"] = step_data["dp2_decision"]

            elif step_name == "validate_feasibility":
                if "overall_score" in step_data:
                    state["feasibility"] = {
                        "overall_score": step_data.get("overall_score", 0),
                        "technical_feasibility": step_data.get("technical_feasibility", 0),
                        "resource_feasibility": step_data.get("resource_feasibility", 0),
                        "timeline_feasibility": step_data.get("timeline_feasibility", 0),
                    }

        # 승인 상태 설정
        state["approval_status"] = ApprovalStatus.APPROVED
        state["approval_decision"] = approval_decision

        return state

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
            await self.job_service.update_progress(
                job=job,
                current_step="thinking",
                progress_percent=progress,
                progress_detail=f"Iteration {iteration}: 다음 행동 결정 중...",
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

    async def _process_event(self, job: AgentJob, event: Any) -> None:
        """스트리밍 이벤트 처리

        Args:
            job: 작업 객체
            event: StudyPlanEvent 객체
        """
        job_id = job.id
        event_type = event.event_type
        event_data = event.data

        # 노드 이름과 진행률 추출
        node_name = event_data.get("node", "")
        progress = NODE_PROGRESS_MAP.get(node_name, job.progress_percent)
        detail = event_data.get("detail", node_name)

        # 이벤트 타입에 따른 처리
        if event_type == StudyPlanEventType.STATUS:
            # 상태 업데이트
            await self.job_service.update_progress(
                job=job,
                current_step=event_data.get("status", "running"),
                progress_percent=progress,
                progress_detail=event_data.get("message"),
            )

        elif event_type == StudyPlanEventType.APPROVAL_REQUIRED:
            # 승인 대기 상태로 전환
            await self._handle_approval_required(job, event_data)
            return  # 승인 대기 후 종료

        elif event_type == StudyPlanEventType.ERROR:
            # 에러 발생
            error_msg = event_data.get("error", "Unknown error")
            await self._handle_failure(job, error=error_msg)
            return

        elif event_type == StudyPlanEventType.DONE:
            # 완료 처리
            await self._handle_done(job, event_data)
            return

        else:
            # 진행 상태 업데이트
            job = await self.job_service.update_progress(
                job=job,
                current_step=node_name or str(event_type.value),
                progress_percent=progress,
                progress_detail=detail,
                step_result=event_data if node_name else None,
            )

        # SSE로 이벤트 전송
        await sse_manager.send_to_job_subscribers(
            job_id=job_id,
            event_type=str(event_type.value),
            data={
                "job_id": str(job_id),
                "event": str(event_type.value),
                "node": node_name,
                "progress_percent": progress,
                "current_step": node_name or str(event_type.value),
                "detail": detail,
                **event_data,
            },
        )

    async def _handle_approval_required(
        self, job: AgentJob, event_data: dict[str, Any]
    ) -> None:
        """승인 대기 처리"""
        job_id = job.id
        user_id = job.user_id

        # 승인 선택지 추출
        choices = event_data.get("choices", [])
        items = event_data.get("items", [])

        # 승인 대기 상태로 전환
        job = await self.job_service.set_waiting_approval(
            job=job,
            gate_id="dp1_approval",
            choices={
                "choices": choices,
                "items": items,
            },
        )

        # 알림 생성
        notification = await self.notification_service.create(
            data=NotificationCreateInternal(
                user_id=user_id,
                type="approval_required",
                category="agent",
                title="승인이 필요합니다",
                message=f"'{job.job_name or job.agent_type}' 작업이 승인을 기다리고 있습니다.",
                entity_type="agent_job",
                entity_id=job_id,
                action_type="approve",
                priority="high",
            )
        )

        # SSE로 승인 요청 이벤트 전송
        await sse_manager.send_to_job_subscribers(
            job_id=job_id,
            event_type="waiting_approval",
            data={
                "job_id": str(job_id),
                "event": "waiting_approval",
                "approval_required": True,
                "approval_gate_id": "dp1_approval",
                "approval_choices": choices,
                "approval_items": items,
            },
        )

        # 알림도 브로드캐스트
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

        logger.info(f"[JobExecutor] Job {job_id} waiting for approval")

    async def _handle_done(self, job: AgentJob, event_data: dict[str, Any]) -> None:
        """완료 처리"""
        job_id = job.id
        user_id = job.user_id

        # 결과 데이터 추출
        result_data = {
            "final_plan": event_data.get("final_plan", ""),
            "executive_summary": event_data.get("executive_summary", ""),
            "plan_a": event_data.get("plan_a", ""),
            "plan_b": event_data.get("plan_b", ""),
            "dp3_decision": event_data.get("dp3_decision", "single_plan"),
            "highest_tier_used": event_data.get("highest_tier_used", 1),
            "success": event_data.get("success", True),
        }

        experiment_count = event_data.get("experiment_count", 0)
        executive_summary = event_data.get("executive_summary", "")
        total_duration = event_data.get("total_duration_ms", 0)

        # 완료 처리
        job = await self.job_service.complete(
            job=job,
            result_data=result_data,
            executive_summary=executive_summary,
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
                "total_duration_ms": total_duration,
                **result_data,
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

        logger.info(f"[JobExecutor] Job {job_id} completed successfully")

    async def _handle_result(self, job: AgentJob, result: Any) -> None:
        """동기 실행 결과 처리 (v4 등)"""
        job_id = job.id

        if result.success:
            result_data = {
                "final_plan": result.final_plan,
                "executive_summary": result.executive_summary,
                "approval_required": result.approval_required,
                "approval_status": result.approval_status,
            }

            job = await self.job_service.complete(
                job=job,
                result_data=result_data,
                executive_summary=result.executive_summary,
                experiment_count=result.experiment_count,
            )

            await sse_manager.send_to_job_subscribers(
                job_id=job_id,
                event_type="completed",
                data={
                    "job_id": str(job_id),
                    "event": "completed",
                    "success": True,
                    **result_data,
                },
            )
        else:
            await self._handle_failure(job, error=result.error or "Unknown error")

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
