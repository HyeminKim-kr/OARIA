"""API 라우터"""

from .auth import router as auth_router
from .papers import router as papers_router
from .ai import router as ai_router
from .lab import router as lab_router
from .paper_chat import router as paper_chat_router

__all__ = ["auth_router", "papers_router", "ai_router", "lab_router", "paper_chat_router"]
