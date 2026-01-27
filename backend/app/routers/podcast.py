"""Podcast API Router.

F-11: Agentic Podcast System
- On-demand generation (SSE streaming)
- Episode CRUD
- Subscription management
"""

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.podcast import (
    PodcastSubscription,
    PodcastEpisode,
    EpisodeStatus,
)
from app.schemas.podcast import (
    PodcastGoalRequest,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
    EpisodeResponse,
    EpisodeListItem,
    SubscriptionResponse,
    PaginatedEpisodes,
    PaginatedSubscriptions,
)
from app.services.podcast import PodcastService, get_podcast_service

router = APIRouter(prefix="/podcast", tags=["podcast"])


# ─────────────────────────────────────────────────────────────
# On-Demand Generation (SSE Streaming)
# ─────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_podcast(
    request: PodcastGoalRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate a podcast episode from a goal (SSE streaming).

    Executes the 3-task pipeline:
    1. RAG Search - Find relevant papers
    2. Paper Analysis - Extract key findings
    3. Script Generation - Create dialogue script

    SSE Events:
    - status: Generation progress status
    - task_start: Task execution started
    - task_complete: Task completed with summary
    - gate2_warning: RAG quality warning (if Gate 2 fails)
    - script: Generated dialogue script
    - done: Generation complete with episode ID
    - error: Generation failed

    Returns:
        SSE stream with generation progress and results
    """
    service = PodcastService(db)

    async def generate_sse():
        """SSE stream generator."""
        async for event in service.generate_episode_stream(
            user_id=current_user.id,
            request=request,
        ):
            yield {
                "event": event.event_type,
                "data": json.dumps(event.data, ensure_ascii=False),
            }

    return EventSourceResponse(generate_sse())


# ─────────────────────────────────────────────────────────────
# Episodes CRUD
# ─────────────────────────────────────────────────────────────


@router.get("/episodes", response_model=PaginatedEpisodes)
async def list_episodes(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """List user's podcast episodes."""
    service = PodcastService(db)
    return await service.list_episodes(
        user_id=current_user.id,
        page=page,
        size=size,
    )


@router.get("/episodes/{episode_id}", response_model=EpisodeResponse)
async def get_episode(
    episode_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a single podcast episode by ID."""
    service = PodcastService(db)
    episode = await service.get_episode(
        user_id=current_user.id,
        episode_id=episode_id,
    )

    if not episode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not found",
        )

    return service.episode_to_response(episode)


@router.delete("/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode(
    episode_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a podcast episode."""
    service = PodcastService(db)
    deleted = await service.delete_episode(
        user_id=current_user.id,
        episode_id=episode_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not found",
        )


# ─────────────────────────────────────────────────────────────
# Subscriptions CRUD
# ─────────────────────────────────────────────────────────────


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    request: SubscriptionCreateRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new podcast subscription for scheduled generation."""
    subscription = PodcastSubscription(
        user_id=current_user.id,
        topics=request.topics,
        frequency=request.frequency,
        episode_style=request.episode_style,
        episode_duration=request.episode_duration,
        language=request.language,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    return subscription


@router.get("/subscriptions", response_model=PaginatedSubscriptions)
async def list_subscriptions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """List user's podcast subscriptions."""
    offset = (page - 1) * size

    # Count total
    count_query = select(func.count()).select_from(PodcastSubscription).where(
        PodcastSubscription.user_id == current_user.id
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Get subscriptions
    query = (
        select(PodcastSubscription)
        .where(PodcastSubscription.user_id == current_user.id)
        .order_by(PodcastSubscription.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(query)
    subscriptions = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedSubscriptions(
        items=[SubscriptionResponse.model_validate(s) for s in subscriptions],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a single subscription by ID."""
    subscription = await db.get(PodcastSubscription, subscription_id)

    if not subscription or subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    return subscription


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: uuid.UUID,
    request: SubscriptionUpdateRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a subscription."""
    subscription = await db.get(PodcastSubscription, subscription_id)

    if not subscription or subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    # Update fields if provided
    if request.topics is not None:
        subscription.topics = request.topics
    if request.frequency is not None:
        subscription.frequency = request.frequency
    if request.episode_style is not None:
        subscription.episode_style = request.episode_style
    if request.episode_duration is not None:
        subscription.episode_duration = request.episode_duration
    if request.language is not None:
        subscription.language = request.language
    if request.is_active is not None:
        subscription.is_active = request.is_active

    await db.commit()
    await db.refresh(subscription)

    return subscription


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a subscription."""
    subscription = await db.get(PodcastSubscription, subscription_id)

    if not subscription or subscription.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    await db.delete(subscription)
    await db.commit()


# ─────────────────────────────────────────────────────────────
# Admin / Manual Trigger (for testing scheduled generation)
# ─────────────────────────────────────────────────────────────


@router.post("/admin/trigger-scheduled")
async def trigger_scheduled_generation(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    subscription_id: uuid.UUID | None = Query(None, description="Specific subscription to trigger"),
):
    """Manually trigger scheduled podcast generation.

    For testing purposes - triggers the scheduled generation task.
    If subscription_id is provided, only generates for that subscription.
    Otherwise, generates for all active subscriptions.

    Returns:
        Dict with status and number of episodes queued
    """
    # In production, this would queue Celery tasks
    # For now, just return a status message

    if subscription_id:
        subscription = await db.get(PodcastSubscription, subscription_id)
        if not subscription or subscription.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found",
            )
        subscriptions = [subscription]
    else:
        query = select(PodcastSubscription).where(
            PodcastSubscription.user_id == current_user.id,
            PodcastSubscription.is_active == True,
        )
        result = await db.execute(query)
        subscriptions = result.scalars().all()

    return {
        "status": "queued",
        "subscriptions_count": len(subscriptions),
        "message": f"Scheduled generation triggered for {len(subscriptions)} subscription(s)",
    }
