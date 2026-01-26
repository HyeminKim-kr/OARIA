"""SSE (Server-Sent Events) 연결 관리

사용자별 SSE 연결을 관리하고 실시간 이벤트를 전송.
- 작업 진행 상태 스트리밍
- 알림 실시간 전송
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class SSEConnection:
    """SSE 연결 정보"""

    user_id: UUID
    connection_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_event_at: datetime | None = None


class SSEManager:
    """SSE 연결 관리자

    싱글톤 패턴으로 전역에서 사용.
    사용자별로 여러 연결을 관리할 수 있음 (여러 탭/디바이스).
    """

    _instance: "SSEManager | None" = None

    def __new__(cls) -> "SSEManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # user_id -> list[SSEConnection]
        self._connections: dict[UUID, list[SSEConnection]] = defaultdict(list)
        # job_id -> list[(user_id, connection_id)] - 특정 작업 구독
        self._job_subscriptions: dict[UUID, list[tuple[UUID, str]]] = defaultdict(list)
        # Lock for thread safety
        self._lock = asyncio.Lock()

    # ============================================================
    # 연결 관리
    # ============================================================

    async def connect(self, user_id: UUID, connection_id: str) -> SSEConnection:
        """새 SSE 연결 등록"""
        async with self._lock:
            connection = SSEConnection(
                user_id=user_id,
                connection_id=connection_id,
            )
            self._connections[user_id].append(connection)
            logger.info(
                f"SSE connected: user={user_id}, conn={connection_id}, "
                f"total_conns={len(self._connections[user_id])}"
            )
            return connection

    async def disconnect(self, user_id: UUID, connection_id: str) -> None:
        """SSE 연결 해제"""
        async with self._lock:
            # 연결 제거
            self._connections[user_id] = [
                c for c in self._connections[user_id] if c.connection_id != connection_id
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]

            # 작업 구독 제거
            for job_id in list(self._job_subscriptions.keys()):
                self._job_subscriptions[job_id] = [
                    (uid, cid)
                    for uid, cid in self._job_subscriptions[job_id]
                    if not (uid == user_id and cid == connection_id)
                ]
                if not self._job_subscriptions[job_id]:
                    del self._job_subscriptions[job_id]

            logger.info(f"SSE disconnected: user={user_id}, conn={connection_id}")

    async def subscribe_job(
        self, user_id: UUID, connection_id: str, job_id: UUID
    ) -> None:
        """특정 작업 구독"""
        async with self._lock:
            sub = (user_id, connection_id)
            if sub not in self._job_subscriptions[job_id]:
                self._job_subscriptions[job_id].append(sub)
                logger.debug(f"Job subscription: user={user_id}, job={job_id}")

    async def unsubscribe_job(
        self, user_id: UUID, connection_id: str, job_id: UUID
    ) -> None:
        """작업 구독 해제"""
        async with self._lock:
            self._job_subscriptions[job_id] = [
                (uid, cid)
                for uid, cid in self._job_subscriptions[job_id]
                if not (uid == user_id and cid == connection_id)
            ]
            if not self._job_subscriptions[job_id]:
                del self._job_subscriptions[job_id]

    # ============================================================
    # 이벤트 전송
    # ============================================================

    async def send_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """사용자의 모든 연결에 이벤트 전송"""
        connections = self._connections.get(user_id, [])
        sent_count = 0

        event = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        for conn in connections:
            try:
                await conn.queue.put(event)
                conn.last_event_at = datetime.utcnow()
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send event to {conn.connection_id}: {e}")

        return sent_count

    async def send_to_job_subscribers(
        self,
        job_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """작업 구독자들에게 이벤트 전송"""
        subscribers = self._job_subscriptions.get(job_id, [])
        sent_count = 0

        event = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        for user_id, connection_id in subscribers:
            connections = self._connections.get(user_id, [])
            for conn in connections:
                if conn.connection_id == connection_id:
                    try:
                        await conn.queue.put(event)
                        conn.last_event_at = datetime.utcnow()
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send event to {connection_id}: {e}")
                    break

        return sent_count

    async def broadcast_notification(
        self,
        user_id: UUID,
        notification_data: dict[str, Any],
    ) -> int:
        """알림 브로드캐스트"""
        return await self.send_to_user(
            user_id=user_id,
            event_type="notification",
            data=notification_data,
        )

    # ============================================================
    # 스트리밍 제너레이터
    # ============================================================

    async def stream_events(
        self,
        connection: SSEConnection,
        heartbeat_interval: int = 30,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """SSE 이벤트 스트림 생성

        클라이언트에게 전송할 SSE 이벤트를 생성.
        하트비트를 통해 연결 유지.

        EventSourceResponse가 dict를 받아서 SSE 형식으로 변환.
        """
        try:
            while True:
                try:
                    # 큐에서 이벤트 대기 (타임아웃으로 하트비트 전송)
                    event = await asyncio.wait_for(
                        connection.queue.get(),
                        timeout=heartbeat_interval,
                    )
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"], default=str, ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    # 하트비트 전송
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"alive": True}),
                    }
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for {connection.connection_id}")
            raise
        except Exception as e:
            logger.error(f"Stream error for {connection.connection_id}: {e}")
            raise

    # ============================================================
    # 유틸리티
    # ============================================================

    def get_user_connection_count(self, user_id: UUID) -> int:
        """사용자 연결 수 조회"""
        return len(self._connections.get(user_id, []))

    def get_total_connection_count(self) -> int:
        """전체 연결 수 조회"""
        return sum(len(conns) for conns in self._connections.values())

    def get_job_subscriber_count(self, job_id: UUID) -> int:
        """작업 구독자 수 조회"""
        return len(self._job_subscriptions.get(job_id, []))


# 싱글톤 인스턴스
sse_manager = SSEManager()
