"""PodcastService - Main orchestrator for podcast generation.

F-11: Agentic Podcast System
Orchestrates the 3-task pipeline:
1. RAG Search (only RAG call)
2. Paper Analysis (LLM)
3. Script Generation (LLM)

Then calls TTS service for audio generation.
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.podcast import (
    PodcastEpisode,
    PodcastSubscription,
    EpisodeStatus,
)
from app.schemas.podcast import (
    PodcastGoalRequest,
    PodcastReference,
    TaskResult,
    TurnTiming as TurnTimingSchema,
    DialogueScript as DialogueScriptSchema,
    DialogueTurn as DialogueTurnSchema,
    EpisodeResponse,
    EpisodeListItem,
    PaginatedEpisodes,
)
from app.schemas.chat import Reference

from .agent import (
    PodcastTaskType,
    PodcastStatus,
    execute_rag_search,
    execute_paper_analysis,
    execute_script_generation,
)
from .agent.tasks.rag_search import format_references_for_podcast
from .tts_service import tts_service, TurnTiming

logger = logging.getLogger(__name__)


@dataclass
class PodcastEvent:
    """Event emitted during podcast generation."""

    event_type: str  # status, task_start, task_complete, script_chunk, done, error
    data: dict[str, Any]


class PodcastService:
    """
    Main service for podcast generation.

    Handles:
    - On-demand podcast generation (SSE streaming)
    - Episode CRUD operations
    - Subscription management
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========================================
    # On-Demand Generation (SSE Streaming)
    # ========================================

    async def generate_episode_stream(
        self,
        user_id: uuid.UUID,
        request: PodcastGoalRequest,
    ) -> AsyncGenerator[PodcastEvent, None]:
        """
        Generate a podcast episode with streaming events.

        Executes the 3-task pipeline:
        1. RAG Search
        2. Paper Analysis
        3. Script Generation

        Then generates audio via TTS (if enabled).

        Args:
            user_id: User ID
            request: Generation request with goal and config

        Yields:
            PodcastEvent for each step
        """
        start_time = time.perf_counter()
        episode_id: uuid.UUID | None = None

        try:
            # Create episode record (pending)
            episode = PodcastEpisode(
                user_id=user_id,
                goal=request.goal,
                duration=request.duration,
                style=request.style,
                paper_mode=request.paper_mode,
                language=request.language,
                search_filters=request.filters.model_dump() if request.filters else None,
                status=EpisodeStatus.PENDING.value,
            )
            self.db.add(episode)
            await self.db.flush()
            episode_id = episode.id

            yield PodcastEvent(
                event_type="status",
                data={"status": "started", "episode_id": str(episode_id)},
            )

            # ========================================
            # Task 1: RAG Search (ONLY RAG CALL)
            # ========================================
            yield PodcastEvent(
                event_type="task_start",
                data={
                    "task_name": "RAG Search",
                    "task_index": 1,
                    "total_tasks": 3,
                },
            )

            episode.status = EpisodeStatus.SEARCHING.value
            await self.db.flush()

            filters = request.filters.model_dump() if request.filters else None
            rag_result = await execute_rag_search(
                goal=request.goal,
                filters=filters,
                top_k=10,
            )

            yield PodcastEvent(
                event_type="task_complete",
                data={
                    "task_name": "RAG Search",
                    "task_index": 1,
                    "duration_ms": rag_result.duration_ms,
                    "summary": f"Found {len(rag_result.references)} relevant papers",
                    "gate2_passed": rag_result.gate2_passed,
                },
            )

            # Check Gate 2
            if not rag_result.gate2_passed:
                yield PodcastEvent(
                    event_type="gate2_warning",
                    data={
                        "passed": False,
                        "reason": rag_result.gate2_reason,
                        "message": "검색된 논문의 관련성이 낮습니다. 생성을 계속하지만 품질이 낮을 수 있습니다.",
                    },
                )

            # ========================================
            # Task 2: Paper Analysis (LLM)
            # ========================================
            yield PodcastEvent(
                event_type="task_start",
                data={
                    "task_name": "Paper Analysis",
                    "task_index": 2,
                    "total_tasks": 3,
                },
            )

            episode.status = EpisodeStatus.ANALYZING.value
            await self.db.flush()

            analysis_result = await execute_paper_analysis(
                goal=request.goal,
                references=rag_result.references,
                context=rag_result.context,
                language=request.language,
            )

            yield PodcastEvent(
                event_type="task_complete",
                data={
                    "task_name": "Paper Analysis",
                    "task_index": 2,
                    "duration_ms": analysis_result.duration_ms,
                    "summary": f"Identified {len(analysis_result.key_findings)} key findings",
                },
            )

            # ========================================
            # Task 3: Script Generation (LLM)
            # ========================================
            yield PodcastEvent(
                event_type="task_start",
                data={
                    "task_name": "Script Generation",
                    "task_index": 3,
                    "total_tasks": 3,
                },
            )

            episode.status = EpisodeStatus.SCRIPTING.value
            await self.db.flush()

            script_result = await execute_script_generation(
                goal=request.goal,
                references=rag_result.references,
                context=rag_result.context,
                analysis_result=analysis_result,
                style=request.style,
                duration=request.duration,
                language=request.language,
            )

            yield PodcastEvent(
                event_type="task_complete",
                data={
                    "task_name": "Script Generation",
                    "task_index": 3,
                    "duration_ms": script_result.duration_ms,
                    "summary": f"Generated {len(script_result.script.get('turns', []))} dialogue turns",
                },
            )

            # ========================================
            # TTS Audio Generation
            # ========================================
            audio_url = None
            audio_duration = None
            tts_error = None
            turn_timings_data: list[dict] = []

            if script_result.script and tts_service.is_enabled:
                yield PodcastEvent(
                    event_type="status",
                    data={"status": "generating_audio", "message": "음성 파일 생성 중..."},
                )

                episode.status = EpisodeStatus.GENERATING_AUDIO.value
                await self.db.flush()

                # Generate audio and get turn timings
                tts_result = await tts_service.generate_dialogue_audio(script_result.script)

                if tts_result.error or not tts_result.audio_data:
                    tts_error = tts_result.error
                else:
                    # Upload to S3
                    try:
                        from app.services.s3_service import s3_service

                        object_key = f"podcast/episodes/{episode.id}/audio.mp3"
                        audio_url = await s3_service.upload_bytes(
                            data=tts_result.audio_data,
                            object_key=object_key,
                            content_type="audio/mpeg",
                        )
                        audio_duration = tts_result.duration_seconds
                    except Exception as e:
                        logger.error(f"Failed to upload podcast audio: {e}")
                        tts_error = f"Upload failed: {e}"
                        audio_duration = tts_result.duration_seconds

                    # Capture turn timings
                    turn_timings_data = [
                        {
                            "turn_index": tt.turn_index,
                            "start_time": round(tt.start_time, 3),
                            "end_time": round(tt.end_time, 3),
                            "speaker": tt.speaker,
                        }
                        for tt in tts_result.turn_timings
                    ]

                if tts_error:
                    logger.warning(f"TTS generation warning: {tts_error}")
                    yield PodcastEvent(
                        event_type="status",
                        data={"status": "tts_warning", "message": f"음성 생성 경고: {tts_error}"},
                    )
                else:
                    yield PodcastEvent(
                        event_type="status",
                        data={"status": "audio_complete", "message": "음성 파일 생성 완료"},
                    )

            # ========================================
            # Update Episode with Results
            # ========================================
            total_duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Convert references to podcast format
            podcast_refs = self._convert_references(rag_result.references)
            paper_ids = list({ref.paper_id for ref in rag_result.references})

            # Store task results
            task_results_data = {
                "rag_search": {
                    "status": rag_result.status,
                    "duration_ms": rag_result.duration_ms,
                    "references_count": len(rag_result.references),
                    "gate2_passed": rag_result.gate2_passed,
                    "gate2_reason": rag_result.gate2_reason,
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
                "total_duration_ms": total_duration_ms,
            }

            # Update episode (inject turn_timings into script JSONB)
            episode.title = script_result.script.get("title") if script_result.script else None
            episode.description = script_result.script.get("description") if script_result.script else None
            script_to_store = dict(script_result.script) if script_result.script else None
            if script_to_store and turn_timings_data:
                script_to_store["turn_timings"] = turn_timings_data
            episode.script = script_to_store
            episode.paper_ids = paper_ids
            episode.references = [ref.model_dump() for ref in podcast_refs]
            episode.task_results = task_results_data
            episode.audio_url = audio_url
            episode.duration_seconds = audio_duration or (script_result.script.get("total_estimated_duration") if script_result.script else None)
            episode.status = EpisodeStatus.COMPLETED.value
            episode.completed_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(episode)

            # Yield script for frontend display
            yield PodcastEvent(
                event_type="script",
                data={
                    "script": script_result.script,
                    "references": [ref.model_dump() for ref in podcast_refs],
                    "turn_timings": turn_timings_data if turn_timings_data else None,
                },
            )

            # Done event
            yield PodcastEvent(
                event_type="done",
                data={
                    "episode_id": str(episode.id),
                    "title": episode.title,
                    "audio_url": episode.audio_url,
                    "duration_seconds": episode.duration_seconds,
                    "total_duration_ms": total_duration_ms,
                    "turn_timings": turn_timings_data if turn_timings_data else None,
                },
            )

        except Exception as e:
            logger.error(f"Podcast generation failed: {e}", exc_info=True)

            # Update episode status to failed
            if episode_id:
                episode = await self.db.get(PodcastEpisode, episode_id)
                if episode:
                    episode.status = EpisodeStatus.FAILED.value
                    episode.error_message = str(e)
                    await self.db.commit()

            yield PodcastEvent(
                event_type="error",
                data={"error": str(e), "episode_id": str(episode_id) if episode_id else None},
            )

    def _convert_references(self, references: list[Reference]) -> list[PodcastReference]:
        """Convert RAG references to podcast reference format."""
        podcast_refs = []
        for idx, ref in enumerate(references, 1):
            podcast_refs.append(
                PodcastReference(
                    index=idx,
                    paper_id=ref.paper_id,
                    title=ref.title,
                    authors=None,  # Not in Reference schema
                    journal=ref.journal,
                    year=ref.year,
                    snippet=ref.snippet,
                )
            )
        return podcast_refs

    # ========================================
    # Episode CRUD Operations
    # ========================================

    async def get_episode(
        self,
        user_id: uuid.UUID,
        episode_id: uuid.UUID,
    ) -> PodcastEpisode | None:
        """Get a single episode by ID."""
        episode = await self.db.get(PodcastEpisode, episode_id)
        if episode and episode.user_id == user_id:
            return episode
        return None

    async def list_episodes(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
    ) -> PaginatedEpisodes:
        """List episodes for a user with pagination."""
        offset = (page - 1) * size

        # Count total
        count_query = select(func.count()).select_from(PodcastEpisode).where(
            PodcastEpisode.user_id == user_id
        )
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get episodes
        query = (
            select(PodcastEpisode)
            .where(PodcastEpisode.user_id == user_id)
            .order_by(PodcastEpisode.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        result = await self.db.execute(query)
        episodes = result.scalars().all()

        items = [
            EpisodeListItem(
                id=ep.id,
                title=ep.title,
                goal=ep.goal,
                status=ep.status,
                duration_seconds=ep.duration_seconds,
                created_at=ep.created_at,
                completed_at=ep.completed_at,
            )
            for ep in episodes
        ]

        pages = (total + size - 1) // size if total > 0 else 0

        return PaginatedEpisodes(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def delete_episode(
        self,
        user_id: uuid.UUID,
        episode_id: uuid.UUID,
    ) -> bool:
        """Delete an episode."""
        episode = await self.get_episode(user_id, episode_id)
        if not episode:
            return False

        await self.db.delete(episode)
        await self.db.commit()
        return True

    def episode_to_response(self, episode: PodcastEpisode) -> EpisodeResponse:
        """Convert Episode model to response schema."""
        # Parse script
        script_schema = None
        if episode.script:
            turns = [
                DialogueTurnSchema(
                    speaker=t.get("speaker", ""),
                    text=t.get("text", ""),
                    citations=t.get("citations"),
                )
                for t in episode.script.get("turns", [])
            ]
            script_schema = DialogueScriptSchema(
                title=episode.script.get("title", ""),
                description=episode.script.get("description", ""),
                speakers=episode.script.get("speakers", []),
                turns=turns,
                total_estimated_duration=episode.script.get("total_estimated_duration", 0),
            )

        # Parse references
        refs = None
        if episode.references:
            refs = [
                PodcastReference(
                    index=r.get("index", 0),
                    paper_id=r.get("paper_id", ""),
                    title=r.get("title", ""),
                    authors=r.get("authors"),
                    journal=r.get("journal"),
                    year=r.get("year"),
                    snippet=r.get("snippet", ""),
                )
                for r in episode.references
            ]

        # Parse task results
        task_results = None
        if episode.task_results:
            task_results = []
            for task_name, task_data in episode.task_results.items():
                if task_name == "total_duration_ms":
                    continue
                task_results.append(
                    TaskResult(
                        task_name=task_name,
                        status=task_data.get("status", "unknown"),
                        duration_ms=task_data.get("duration_ms", 0),
                        output_summary=None,
                        error=task_data.get("error"),
                    )
                )

        # Parse turn_timings from script JSONB
        turn_timings = None
        if episode.script and "turn_timings" in episode.script:
            turn_timings = [
                TurnTimingSchema(
                    turn_index=tt.get("turn_index", 0),
                    start_time=tt.get("start_time", 0.0),
                    end_time=tt.get("end_time", 0.0),
                    speaker=tt.get("speaker", ""),
                )
                for tt in episode.script["turn_timings"]
            ]

        return EpisodeResponse(
            id=episode.id,
            goal=episode.goal,
            title=episode.title,
            description=episode.description,
            status=episode.status,
            duration=episode.duration,
            style=episode.style,
            language=episode.language,
            audio_url=episode.audio_url,
            duration_seconds=episode.duration_seconds,
            script=script_schema,
            references=refs,
            turn_timings=turn_timings,
            paper_ids=episode.paper_ids,
            task_results=task_results,
            created_at=episode.created_at,
            completed_at=episode.completed_at,
        )


# Dependency injection
def get_podcast_service(db: AsyncSession) -> PodcastService:
    """Get podcast service instance."""
    return PodcastService(db)
