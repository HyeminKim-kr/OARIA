"""Notification 서비스

알림 생성, 조회, 상태 관리.
- 알림 CRUD
- SSE 실시간 알림 발송
- 읽음 처리
"""

import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent_job import AgentJob, AgentJobStatus
from ..models.notification import (
    Notification,
    NotificationActionType,
    NotificationCategory,
    NotificationPriority,
    NotificationType,
)
from ..schemas.notification import (
    NotificationCreateInternal,
    NotificationListItem,
    PaginatedNotifications,
)


class NotificationService:
    """Notification CRUD 및 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # CRUD 메서드
    # ============================================================

    async def create(self, data: NotificationCreateInternal) -> Notification:
        """알림 생성"""
        notification = Notification(
            user_id=data.user_id,
            type=data.type,
            category=data.category,
            title=data.title,
            message=data.message,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            action_type=data.action_type,
            action_url=data.action_url,
            action_label=data.action_label,
            priority=data.priority,
            icon=data.icon,
            extra_data=data.extra_data,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        """ID로 알림 조회"""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self, notification_id: UUID, user_id: UUID
    ) -> Notification | None:
        """사용자 소유 알림 조회"""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        category_filter: str | None = None,
        include_dismissed: bool = False,
    ) -> PaginatedNotifications:
        """사용자 알림 목록 조회"""
        # 기본 필터
        conditions = [Notification.user_id == user_id]

        if not include_dismissed:
            conditions.append(Notification.is_dismissed == False)

        if category_filter:
            conditions.append(Notification.category == category_filter)

        # 전체 개수 조회
        count_query = (
            select(func.count()).select_from(Notification).where(and_(*conditions))
        )
        total = (await self.db.execute(count_query)).scalar() or 0

        # 읽지 않은 알림 수 조회
        unread_conditions = conditions + [Notification.is_read == False]
        unread_query = (
            select(func.count())
            .select_from(Notification)
            .where(and_(*unread_conditions))
        )
        unread_count = (await self.db.execute(unread_query)).scalar() or 0

        # 페이지네이션 계산
        pages = math.ceil(total / size) if total > 0 else 1
        offset = (page - 1) * size

        # 데이터 조회
        query = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        result = await self.db.execute(query)
        notifications = result.scalars().all()

        # 응답 변환
        items = [
            NotificationListItem(
                id=n.id,
                type=n.type,
                category=n.category,
                title=n.title,
                message=n.message,
                priority=n.priority,
                icon=n.icon,
                entity_type=n.entity_type,
                entity_id=n.entity_id,
                action_type=n.action_type,
                action_url=n.action_url,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in notifications
        ]

        return PaginatedNotifications(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            unread_count=unread_count,
        )

    async def get_unread_count(self, user_id: UUID) -> int:
        """읽지 않은 알림 수 조회"""
        result = await self.db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    Notification.is_dismissed == False,
                )
            )
        )
        return result.scalar() or 0

    # ============================================================
    # 상태 변경 메서드
    # ============================================================

    async def mark_as_read(self, notification: Notification) -> Notification:
        """알림 읽음 처리"""
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(notification)
        return notification

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """모든 알림 읽음 처리"""
        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                    Notification.is_dismissed == False,
                )
            )
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()
        return result.rowcount  # type: ignore

    async def dismiss(self, notification: Notification) -> Notification:
        """알림 숨기기"""
        notification.is_dismissed = True
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def dismiss_many(self, user_id: UUID, notification_ids: list[UUID]) -> int:
        """여러 알림 숨기기"""
        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.id.in_(notification_ids),
                )
            )
            .values(is_dismissed=True)
        )
        await self.db.commit()
        return result.rowcount  # type: ignore

    # ============================================================
    # 알림 생성 헬퍼 메서드 (Agent Job 관련)
    # ============================================================

    async def notify_job_started(self, job: AgentJob) -> Notification:
        """작업 시작 알림"""
        return await self.create(
            NotificationCreateInternal(
                user_id=job.user_id,
                type=NotificationType.JOB_STARTED.value,
                category=NotificationCategory.AGENT.value,
                title="작업이 시작되었습니다",
                message=f"{job.job_name or job.agent_type} 작업이 시작되었습니다.",
                entity_type="agent_job",
                entity_id=job.id,
                action_type=NotificationActionType.VIEW.value,
                action_url=f"/agents/study-plan/jobs/{job.id}",
                action_label="상세 보기",
                priority=NotificationPriority.NORMAL.value,
                icon="play",
                extra_data={"agent_type": job.agent_type},
            )
        )

    async def notify_job_waiting_approval(self, job: AgentJob) -> Notification:
        """승인 대기 알림"""
        return await self.create(
            NotificationCreateInternal(
                user_id=job.user_id,
                type=NotificationType.JOB_WAITING_APPROVAL.value,
                category=NotificationCategory.AGENT.value,
                title="승인이 필요합니다",
                message=f"{job.job_name or job.agent_type} 작업이 승인을 기다리고 있습니다.",
                entity_type="agent_job",
                entity_id=job.id,
                action_type=NotificationActionType.APPROVE.value,
                action_url=f"/agents/study-plan/jobs/{job.id}/approve",
                action_label="승인하기",
                priority=NotificationPriority.HIGH.value,
                icon="alert-circle",
                extra_data={
                    "agent_type": job.agent_type,
                    "gate_id": job.approval_gate_id,
                },
            )
        )

    async def notify_job_completed(self, job: AgentJob) -> Notification:
        """작업 완료 알림"""
        return await self.create(
            NotificationCreateInternal(
                user_id=job.user_id,
                type=NotificationType.JOB_COMPLETED.value,
                category=NotificationCategory.AGENT.value,
                title="작업이 완료되었습니다",
                message=f"{job.job_name or job.agent_type} 작업이 성공적으로 완료되었습니다.",
                entity_type="agent_job",
                entity_id=job.id,
                action_type=NotificationActionType.VIEW.value,
                action_url=f"/agents/study-plan/jobs/{job.id}",
                action_label="결과 보기",
                priority=NotificationPriority.NORMAL.value,
                icon="check-circle",
                extra_data={
                    "agent_type": job.agent_type,
                    "experiment_count": job.experiment_count,
                    "duration_ms": job.total_duration_ms,
                },
            )
        )

    async def notify_job_failed(self, job: AgentJob) -> Notification:
        """작업 실패 알림"""
        can_retry = job.can_retry
        return await self.create(
            NotificationCreateInternal(
                user_id=job.user_id,
                type=NotificationType.JOB_FAILED.value,
                category=NotificationCategory.AGENT.value,
                title="작업이 실패했습니다",
                message=f"{job.job_name or job.agent_type} 작업 실행 중 오류가 발생했습니다.",
                entity_type="agent_job",
                entity_id=job.id,
                action_type=NotificationActionType.RETRY.value if can_retry else NotificationActionType.VIEW.value,
                action_url=f"/agents/study-plan/jobs/{job.id}",
                action_label="재시도" if can_retry else "상세 보기",
                priority=NotificationPriority.HIGH.value,
                icon="x-circle",
                extra_data={
                    "agent_type": job.agent_type,
                    "error_code": job.last_error_code,
                    "can_retry": can_retry,
                    "attempt_count": job.attempt_count,
                    "max_attempts": job.max_attempts,
                },
            )
        )
