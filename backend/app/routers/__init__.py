"""API 라우터"""

from .auth import router as auth_router
from .papers import router as papers_router
from .ai import router as ai_router
from .lab import router as lab_router
from .paper_chat import router as paper_chat_router
from .study_plan import router as study_plan_router
from .agent_jobs import router as agent_jobs_router
from .notifications import router as notifications_router

__all__ = [
    "auth_router",
    "papers_router",
    "ai_router",
    "lab_router",
    "paper_chat_router",
    "study_plan_router",
    "agent_jobs_router",
    "notifications_router",
]
