"""Like & Bookmark API 스키마"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# Like 스키마
# ============================================================
class LikeResponse(BaseModel):
    """좋아요 토글 응답"""

    paper_id: UUID
    is_liked: bool
    like_count: int


class LikedPaperItem(BaseModel):
    """좋아요한 논문 아이템"""

    paper_id: UUID
    paper_str_id: str
    title: str
    abstract: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[int] = None
    liked_at: datetime

    model_config = {"from_attributes": True}


class PaginatedLikedPapers(BaseModel):
    """좋아요 목록 (페이지네이션)"""

    items: list[LikedPaperItem]
    total: int
    page: int
    limit: int
    total_pages: int


# ============================================================
# Bookmark 스키마
# ============================================================
class BookmarkResponse(BaseModel):
    """북마크 토글 응답"""

    paper_id: UUID
    is_bookmarked: bool
    bookmark_id: Optional[UUID] = None
    collection_id: Optional[UUID] = None


class BookmarkRequest(BaseModel):
    """북마크 요청 (옵션: 컬렉션 지정)"""

    collection_id: Optional[UUID] = Field(None, description="컬렉션 ID (없으면 기본 컬렉션)")


class BookmarkMoveRequest(BaseModel):
    """북마크 컬렉션 이동 요청"""

    collection_id: Optional[UUID] = Field(None, description="이동할 컬렉션 ID")


class BookmarkedPaperItem(BaseModel):
    """북마크한 논문 아이템"""

    bookmark_id: UUID
    paper_id: UUID
    paper_str_id: str
    title: str
    abstract: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[int] = None
    collection_id: Optional[UUID] = None
    collection_name: Optional[str] = None
    bookmarked_at: datetime

    model_config = {"from_attributes": True}


class PaginatedBookmarkedPapers(BaseModel):
    """북마크 목록 (페이지네이션)"""

    items: list[BookmarkedPaperItem]
    total: int
    page: int
    limit: int
    total_pages: int


# ============================================================
# Collection 스키마
# ============================================================
class CollectionCreate(BaseModel):
    """컬렉션 생성"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class CollectionUpdate(BaseModel):
    """컬렉션 수정"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class CollectionResponse(BaseModel):
    """컬렉션 응답"""

    id: UUID
    name: str
    description: Optional[str] = None
    is_default: bool
    sort_order: int
    bookmark_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionListResponse(BaseModel):
    """컬렉션 목록"""

    items: list[CollectionResponse]
    total: int


# ============================================================
# Bulk Interaction Status (논문 목록용)
# ============================================================
class PaperInteractionStatus(BaseModel):
    """논문별 좋아요/북마크 상태"""

    paper_id: UUID
    is_liked: bool = False
    is_bookmarked: bool = False
    like_count: int = 0


class BulkInteractionStatusRequest(BaseModel):
    """여러 논문 상태 일괄 조회 요청"""

    paper_ids: list[UUID]


class BulkInteractionStatusResponse(BaseModel):
    """여러 논문 상태 일괄 응답"""

    statuses: dict[str, PaperInteractionStatus]
