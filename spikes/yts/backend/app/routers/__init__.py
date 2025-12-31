"""API 라우터"""

from .auth import router as auth_router
from .papers import router as papers_router

__all__ = ["auth_router", "papers_router"]
