"""Celery Tasks for Scheduled Podcast Generation.

F-11: Agentic Podcast System
Automated podcast generation based on subscriptions.
"""

import logging
from datetime import datetime
from typing import Any

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.database import async_session_maker
from app.models.podcast import (
    PodcastSubscription,
    PodcastEpisode,
    PodcastFrequency,
    EpisodeStatus,
)
from app.schemas.podcast import PodcastGoalRequest, PodcastFilters
from app.services.notification_service import notification_service

from ..service import PodcastService
from .goal_generator import (
    generate_goal_with_llm,
    should_generate_for_subscription,
)

logger = logging.getLogger(__name__)


async def _generate_episode_for_subscription(
    db: AsyncSession,
    subscription: PodcastSubscription,
) -> PodcastEpisode | None:
    """
    Generate a podcast episode for a single subscription.

    Internal helper function - runs within async context.
    """
    try:
        # Generate goal from topics
        goal = await generate_goal_with_llm(subscription)

        logger.info(
            f"Generating podcast for subscription {subscription.id}",
            extra={
                "user_id": str(subscription.user_id),
                "topics": subscription.topics,
                "goal": goal,
            },
        )

        # Create request
        request = PodcastGoalRequest(
            goal=goal,
            duration=subscription.episode_duration,
            style=subscription.episode_style,
            paper_mode="auto",
            language=subscription.language,
            filters=None,  # Could add default filters based on topics
        )

        # Create service and generate (non-streaming)
        service = PodcastService(db)

        # For scheduled generation, we don't need streaming
        # Execute the full pipeline and save results
        episode = PodcastEpisode(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            goal=goal,
            duration=request.duration,
            style=request.style,
            paper_mode=request.paper_mode,
            language=request.language,
            status=EpisodeStatus.PENDING.value,
        )
        db.add(episode)
        await db.flush()

        # Execute generation pipeline
        try:
            # Import tasks here to avoid circular imports
            from ..langgraph import execute_rag_search, execute_paper_analysis, execute_script_generation

            # Task 1: RAG Search
            episode.status = EpisodeStatus.SEARCHING.value
            await db.flush()

            rag_result = await execute_rag_search(goal=goal, filters=None, top_k=10)

            if rag_result.status == "failed":
                raise Exception(f"RAG search failed: {rag_result.error}")

            # Task 2: Paper Analysis
            episode.status = EpisodeStatus.ANALYZING.value
            await db.flush()

            analysis_result = await execute_paper_analysis(
                goal=goal,
                references=rag_result.references,
                context=rag_result.context,
                language=request.language,
            )

            if analysis_result.status == "failed":
                raise Exception(f"Paper analysis failed: {analysis_result.error}")

            # Task 3: Script Generation
            episode.status = EpisodeStatus.SCRIPTING.value
            await db.flush()

            script_result = await execute_script_generation(
                goal=goal,
                references=rag_result.references,
                context=rag_result.context,
                analysis_result=analysis_result,
                style=request.style,
                duration=request.duration,
                language=request.language,
            )

            if script_result.status == "failed":
                raise Exception(f"Script generation failed: {script_result.error}")

            # Update episode with results
            episode.title = script_result.script.get("title") if script_result.script else None
            episode.description = script_result.script.get("description") if script_result.script else None
            episode.script = script_result.script
            episode.paper_ids = list({ref.paper_id for ref in rag_result.references})
            episode.references = [
                {
                    "index": idx,
                    "paper_id": ref.paper_id,
                    "title": ref.title,
                    "journal": ref.journal,
                    "year": ref.year,
                    "snippet": ref.snippet,
                }
                for idx, ref in enumerate(rag_result.references, 1)
            ]
            episode.task_results = {
                "rag_search": {
                    "status": rag_result.status,
                    "duration_ms": rag_result.duration_ms,
                    "references_count": len(rag_result.references),
                    "gate2_passed": rag_result.gate2_passed,
                },
                "paper_analysis": {
                    "status": analysis_result.status,
                    "duration_ms": analysis_result.duration_ms,
                    "key_findings_count": len(analysis_result.key_findings),
                },
                "script_generation": {
                    "status": script_result.status,
                    "duration_ms": script_result.duration_ms,
                    "turns_count": len(script_result.script.get("turns", [])) if script_result.script else 0,
                },
            }
            episode.duration_seconds = script_result.script.get("total_estimated_duration") if script_result.script else None
            episode.status = EpisodeStatus.COMPLETED.value
            episode.completed_at = datetime.utcnow()

            # Update subscription last_generated_at
            subscription.last_generated_at = datetime.utcnow()

            await db.commit()
            await db.refresh(episode)

            # Send notification to user
            await notification_service.create_notification(
                db=db,
                user_id=subscription.user_id,
                type="podcast_ready",
                title="새 팟캐스트 에피소드가 생성되었습니다" if request.language == "ko" else "New podcast episode ready",
                message=episode.title or goal,
                data={
                    "episode_id": str(episode.id),
                    "subscription_id": str(subscription.id),
                },
            )

            logger.info(f"Scheduled podcast generated: {episode.id}")
            return episode

        except Exception as e:
            episode.status = EpisodeStatus.FAILED.value
            episode.error_message = str(e)
            await db.commit()
            raise

    except Exception as e:
        logger.error(
            f"Failed to generate podcast for subscription {subscription.id}: {e}",
            exc_info=True,
        )
        return None


@celery_app.task(name="app.services.agent.podcast.core.scheduler.generate_daily_podcasts")
def generate_daily_podcasts() -> dict[str, Any]:
    """
    Celery task: Generate podcasts for daily subscriptions.

    Runs at 6 AM UTC daily via beat scheduler.
    """
    import asyncio

    async def _run():
        async with async_session_maker() as db:
            # Get all active daily subscriptions
            query = select(PodcastSubscription).where(
                PodcastSubscription.is_active == True,
                PodcastSubscription.frequency == PodcastFrequency.DAILY.value,
            )
            result = await db.execute(query)
            subscriptions = result.scalars().all()

            generated = 0
            failed = 0

            for subscription in subscriptions:
                if should_generate_for_subscription(subscription):
                    episode = await _generate_episode_for_subscription(db, subscription)
                    if episode:
                        generated += 1
                    else:
                        failed += 1

            return {
                "frequency": "daily",
                "total_subscriptions": len(subscriptions),
                "generated": generated,
                "failed": failed,
            }

    return asyncio.run(_run())


@celery_app.task(name="app.services.agent.podcast.core.scheduler.generate_weekly_digests")
def generate_weekly_digests() -> dict[str, Any]:
    """
    Celery task: Generate podcasts for weekly subscriptions.

    Runs at 7 AM UTC every Monday via beat scheduler.
    """
    import asyncio

    async def _run():
        async with async_session_maker() as db:
            # Get all active weekly subscriptions
            query = select(PodcastSubscription).where(
                PodcastSubscription.is_active == True,
                PodcastSubscription.frequency == PodcastFrequency.WEEKLY.value,
            )
            result = await db.execute(query)
            subscriptions = result.scalars().all()

            generated = 0
            failed = 0

            for subscription in subscriptions:
                if should_generate_for_subscription(subscription):
                    episode = await _generate_episode_for_subscription(db, subscription)
                    if episode:
                        generated += 1
                    else:
                        failed += 1

            return {
                "frequency": "weekly",
                "total_subscriptions": len(subscriptions),
                "generated": generated,
                "failed": failed,
            }

    return asyncio.run(_run())


@celery_app.task(name="app.services.agent.podcast.core.scheduler.generate_for_subscription")
def generate_for_subscription(subscription_id: str) -> dict[str, Any]:
    """
    Celery task: Generate podcast for a specific subscription.

    Can be triggered manually or by API.
    """
    import asyncio
    import uuid

    async def _run():
        async with async_session_maker() as db:
            subscription = await db.get(
                PodcastSubscription,
                uuid.UUID(subscription_id),
            )

            if not subscription:
                return {"error": "Subscription not found"}

            if not subscription.is_active:
                return {"error": "Subscription is not active"}

            episode = await _generate_episode_for_subscription(db, subscription)

            if episode:
                return {
                    "status": "success",
                    "episode_id": str(episode.id),
                    "title": episode.title,
                }
            else:
                return {"status": "failed"}

    return asyncio.run(_run())
