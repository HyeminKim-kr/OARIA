"""Podcast service module.

F-11: Agentic Podcast System
- Goal-driven podcast generation
- Fixed 3-task agent (RAG → Analysis → Script)
- TTS audio generation
- Scheduled generation via Celery
"""

from .service import PodcastService, PodcastEvent, get_podcast_service
from .core.tts import TTSService, TTSResult, tts_service, get_tts_service
from .core.goal_generator import (
    generate_goal_from_template,
    generate_goal_with_llm,
    should_generate_for_subscription,
)

__all__ = [
    # Service
    "PodcastService",
    "PodcastEvent",
    "get_podcast_service",
    # TTS
    "TTSService",
    "TTSResult",
    "tts_service",
    "get_tts_service",
    # Goal generation
    "generate_goal_from_template",
    "generate_goal_with_llm",
    "should_generate_for_subscription",
]
