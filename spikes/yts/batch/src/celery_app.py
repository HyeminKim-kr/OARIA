"""Celery 앱 설정"""

from celery import Celery

from .config import settings

app = Celery(
    "oaria_batch",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=["src.tasks.backfill"],
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
    },
    # 기본 큐
    task_default_queue="backfill",
)

# Celery Beat 스케줄 (나중에 활성화)
# app.conf.beat_schedule = {
#     'incremental-daily': {
#         'task': 'src.tasks.incremental.run_incremental',
#         'schedule': crontab(hour=3, minute=0),
#     },
#     'repair-weekly': {
#         'task': 'src.tasks.repair.run_repair',
#         'schedule': crontab(hour=2, minute=0, day_of_week=0),
#     },
# }
