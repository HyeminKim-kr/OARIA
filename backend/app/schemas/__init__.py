"""Pydantic 스키마"""

from .auth import TokenResponse
from .user import UserCreate, UserResponse, UserUpdate
from .paper import (
    PaperListItem,
    PaperDetail,
    PaginatedResponse,
    PaperStats,
    AuthorResponse,
)
from .chat import (
    Reference,
    AskFilters,
    AskRequest,
    AskReferencesEvent,
    AskTokenEvent,
    AskDoneEvent,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListItem,
    MessageCreate,
    MessageResponse,
    AnswerLogResponse,
    PaginatedConversations,
    PaginatedMessages,
)

__all__ = [
    # Auth
    "TokenResponse",
    # User
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Paper
    "PaperListItem",
    "PaperDetail",
    "PaginatedResponse",
    "PaperStats",
    "AuthorResponse",
    # Chat
    "Reference",
    "AskFilters",
    "AskRequest",
    "AskReferencesEvent",
    "AskTokenEvent",
    "AskDoneEvent",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
    "ConversationListItem",
    "MessageCreate",
    "MessageResponse",
    "AnswerLogResponse",
    "PaginatedConversations",
    "PaginatedMessages",
]
