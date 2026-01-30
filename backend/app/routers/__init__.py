"""API 라우터"""

from .auth import router as auth_router
from .papers import router as papers_router
from .ai import router as ai_router
from .lab import router as lab_router
from .paper_chat import router as paper_chat_router
from .agent_jobs import router as agent_jobs_router
from .notifications import router as notifications_router
from .podcast import router as podcast_router
from .interactions import router as interactions_router

__all__ = [
    "auth_router",
    "papers_router",
    "ai_router",
    "lab_router",
    "paper_chat_router",
    "agent_jobs_router",
    "notifications_router",
    "podcast_router",
    "interactions_router",
]
