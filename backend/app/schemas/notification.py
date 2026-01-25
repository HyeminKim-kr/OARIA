"""Notification 스키마

알림 API 요청/응답 스키마.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 응답 스키마
# ============================================================


class NotificationResponse(BaseModel):
    """Notification 기본 응답"""

    id: UUID
    type: str
    category: str
    title: str
    message: str

    # Entity Reference
    entity_type: str | None
    entity_id: UUID | None

    # Action
    action_type: str | None
    action_url: str | None
    action_label: str | None

    # Display
    priority: str
    icon: str | None
    extra_data: dict[str, Any] | None

    # Read Status
    is_read: bool
    read_at: datetime | None

    # Timing
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListItem(BaseModel):
    """Notification 목록 아이템 (간략)"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    category: str
    title: str
    message: str
    priority: str
    icon: str | None

    entity_type: str | None
    entity_id: UUID | None
    action_type: str | None
    action_url: str | None

    is_read: bool
    created_at: datetime


class PaginatedNotifications(BaseModel):
    """페이지네이션된 Notification 목록"""

    items: list[NotificationListItem]
    total: int
    page: int
    size: int
    pages: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """읽지 않은 알림 수 응답"""

    count: int


# ============================================================
# 요청 스키마
# ============================================================


class MarkReadRequest(BaseModel):
    """읽음 표시 요청"""

    notification_ids: list[UUID] = Field(
        default=[],
        description="읽음 처리할 알림 ID 목록 (비어있으면 전체 읽음)",
    )


class DismissRequest(BaseModel):
    """알림 숨기기 요청"""

    notification_ids: list[UUID] = Field(
        ...,
        description="숨길 알림 ID 목록",
    )


# ============================================================
# SSE 이벤트 스키마
# ============================================================


class NotificationSSEEvent(BaseModel):
    """SSE 실시간 알림 이벤트"""

    event_type: str = Field(
        ...,
        description="이벤트 유형 (new_notification, unread_count_update)",
    )
    notification: NotificationListItem | None = Field(
        default=None,
        description="새 알림 (new_notification 타입인 경우)",
    )
    unread_count: int | None = Field(
        default=None,
        description="읽지 않은 알림 수",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
    )


# ============================================================
# 내부용 스키마 (서비스에서 사용)
# ============================================================


class NotificationCreateInternal(BaseModel):
    """알림 생성 내부 요청"""

    user_id: UUID
    type: str
    category: str
    title: str
    message: str

    entity_type: str | None = None
    entity_id: UUID | None = None

    action_type: str | None = None
    action_url: str | None = None
    action_label: str | None = None

    priority: str = "normal"
    icon: str | None = None
    extra_data: dict[str, Any] | None = None
