"""Notifications 라우터

알림 관리 엔드포인트.
- 알림 목록 조회
- 읽음/숨기기 처리
- SSE 실시간 알림 스트리밍
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.sse_manager import sse_manager
from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.notification import (
    DismissRequest,
    MarkReadRequest,
    NotificationResponse,
    PaginatedNotifications,
    UnreadCountResponse,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ─────────────────────────────────────────────────────────────
# List Notifications
# ─────────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedNotifications)
async def list_notifications(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    size: int = 20,
    category: str | None = None,
    include_dismissed: bool = False,
):
    """알림 목록 조회

    Args:
        page: 페이지 번호 (1부터 시작)
        size: 페이지당 항목 수 (기본 20, 최대 50)
        category: 카테고리 필터 (agent, paper, system)
        include_dismissed: 숨긴 알림 포함 여부
    """
    if size > 50:
        size = 50
    if page < 1:
        page = 1

    notification_service = NotificationService(db)
    return await notification_service.get_list(
        user_id=current_user.id,
        page=page,
        size=size,
        category_filter=category,
        include_dismissed=include_dismissed,
    )


# ─────────────────────────────────────────────────────────────
# Get Unread Count
# ─────────────────────────────────────────────────────────────


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """읽지 않은 알림 수 조회"""
    notification_service = NotificationService(db)
    count = await notification_service.get_unread_count(current_user.id)
    return UnreadCountResponse(count=count)


# ─────────────────────────────────────────────────────────────
# Stream Notifications (SSE)
# ─────────────────────────────────────────────────────────────


@router.get("/stream")
async def stream_notifications(
    current_user: CurrentUser,
):
    """실시간 알림 SSE 스트리밍

    새로운 알림이 발생하면 실시간으로 전송됩니다.
    30초마다 하트비트가 전송되어 연결을 유지합니다.

    **SSE 이벤트 타입:**
    - `notification`: 새 알림
    - `unread_count`: 읽지 않은 수 업데이트
    - `heartbeat`: 연결 유지
    """
    # SSE 연결 등록
    connection_id = f"{current_user.id}-notifications-{uuid.uuid4().hex[:8]}"
    connection = await sse_manager.connect(current_user.id, connection_id)

    async def generate_events():
        try:
            async for event_str in sse_manager.stream_events(connection):
                yield event_str
        finally:
            await sse_manager.disconnect(current_user.id, connection_id)

    return EventSourceResponse(generate_events())


# ─────────────────────────────────────────────────────────────
# Get Notification Detail
# ─────────────────────────────────────────────────────────────


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """알림 상세 조회"""
    notification_service = NotificationService(db)
    notification = await notification_service.get_by_id_for_user(
        notification_id=notification_id,
        user_id=current_user.id,
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림을 찾을 수 없습니다.",
        )

    return notification


# ─────────────────────────────────────────────────────────────
# Mark as Read
# ─────────────────────────────────────────────────────────────


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """알림 읽음 처리"""
    notification_service = NotificationService(db)
    notification = await notification_service.get_by_id_for_user(
        notification_id=notification_id,
        user_id=current_user.id,
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림을 찾을 수 없습니다.",
        )

    notification = await notification_service.mark_as_read(notification)
    return notification


@router.post("/read-all")
async def mark_all_as_read(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """모든 알림 읽음 처리"""
    notification_service = NotificationService(db)
    count = await notification_service.mark_all_as_read(current_user.id)

    # SSE로 읽지 않은 수 업데이트 브로드캐스트
    await sse_manager.send_to_user(
        user_id=current_user.id,
        event_type="unread_count",
        data={"count": 0},
    )

    return {"message": f"{count}개의 알림이 읽음 처리되었습니다."}


# ─────────────────────────────────────────────────────────────
# Dismiss Notification
# ─────────────────────────────────────────────────────────────


@router.post("/{notification_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_notification(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """알림 숨기기"""
    notification_service = NotificationService(db)
    notification = await notification_service.get_by_id_for_user(
        notification_id=notification_id,
        user_id=current_user.id,
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알림을 찾을 수 없습니다.",
        )

    await notification_service.dismiss(notification)

    # SSE로 읽지 않은 수 업데이트
    if not notification.is_read:
        unread_count = await notification_service.get_unread_count(current_user.id)
        await sse_manager.send_to_user(
            user_id=current_user.id,
            event_type="unread_count",
            data={"count": unread_count},
        )


@router.post("/dismiss-many")
async def dismiss_many_notifications(
    request: DismissRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """여러 알림 숨기기"""
    notification_service = NotificationService(db)
    count = await notification_service.dismiss_many(
        user_id=current_user.id,
        notification_ids=request.notification_ids,
    )

    # SSE로 읽지 않은 수 업데이트
    unread_count = await notification_service.get_unread_count(current_user.id)
    await sse_manager.send_to_user(
        user_id=current_user.id,
        event_type="unread_count",
        data={"count": unread_count},
    )

    return {"message": f"{count}개의 알림이 숨김 처리되었습니다."}
