"""Celery 앱 설정"""

from celery import Celery
from celery.schedules import crontab

from .config import settings

app = Celery(
    "oaria_batch",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=["src.tasks.backfill", "src.tasks.embed"],
)

# Celery 설정
app.conf.update(
    # 태스크 설정
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    # 워커 설정
    worker_prefetch_multiplier=1,  # 한 번에 하나씩 가져오기
    task_acks_late=True,  # 완료 후 ACK
    task_reject_on_worker_lost=True,  # 워커 죽으면 재시도
    # 큐 라우팅
    task_routes={
        "src.tasks.backfill.*": {"queue": "backfill"},
        "src.tasks.incremental.*": {"queue": "incremental"},
        "src.tasks.repair.*": {"queue": "repair"},
        "src.tasks.embed.*": {"queue": "embed"},
    },
    # 기본 큐
    task_default_queue="backfill",
    # Celery Beat 스케줄
    beat_schedule={
        # 매시간 새 논문 임베딩 (최대 50개씩)
        "embed-hourly": {
            "task": "src.tasks.embed.run_embed",
            "schedule": crontab(minute=0),  # 매시 정각
            "args": [None, 50],  # query_id=None, limit=50
            "options": {"queue": "embed"},
        },
        # 매일 새벽 3시 실패한 논문 재임베딩
        "reembed-daily": {
            "task": "src.tasks.embed.run_reembed",
            "schedule": crontab(hour=3, minute=0),
            "args": [None, None],  # query_id=None, limit=None (전체)
            "options": {"queue": "embed"},
        },
    },
)
