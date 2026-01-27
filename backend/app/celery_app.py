"""Celery application configuration.

F-11: Agentic Podcast System
Celery worker and beat scheduler for automated podcast generation.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings


# Create Celery app
celery_app = Celery(
    "oaria",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Results
    result_expires=86400,  # 24 hours

    # Worker
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_concurrency=2,  # 2 concurrent workers for podcast generation

    # Beat scheduler
    beat_schedule={
        # Daily podcast generation (6 AM UTC)
        "podcast-daily-generation": {
            "task": "app.services.podcast.scheduler.generate_daily_podcasts",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "podcast"},
        },
        # Weekly digest (Monday 7 AM UTC)
        "podcast-weekly-digest": {
            "task": "app.services.podcast.scheduler.generate_weekly_digests",
            "schedule": crontab(day_of_week=1, hour=7, minute=0),
            "options": {"queue": "podcast"},
        },
    },

    # Queues
    task_default_queue="default",
    task_queues={
        "default": {},
        "podcast": {
            "exchange": "podcast",
            "routing_key": "podcast",
        },
    },
    task_routes={
        "app.services.podcast.scheduler.*": {"queue": "podcast"},
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "app.services.podcast",
])
