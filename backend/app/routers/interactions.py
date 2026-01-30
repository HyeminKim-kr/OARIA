"""Like & Bookmark API 라우터

좋아요, 북마크, 컬렉션 CRUD 엔드포인트
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import CurrentUser
from ..models.paper import Paper
from ..schemas.interaction import (
    BulkInteractionStatusRequest,
    BulkInteractionStatusResponse,
    BookmarkMoveRequest,
    BookmarkRequest,
    BookmarkResponse,
    CollectionCreate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
    LikeResponse,
    PaginatedBookmarkedPapers,
    PaginatedLikedPapers,
    PaperInteractionStatus,
)
from ..services.interaction_service import InteractionService

router = APIRouter(tags=["interactions"])


# ============================================================
# Like
# ============================================================
@router.post("/papers/{paper_id}/like", response_model=LikeResponse)
async def toggle_like(
    paper_id: UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """논문 좋아요 토글 (좋아요 <-> 취소)"""
    result = await db.execute(select(Paper.id).where(Paper.id == paper_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Paper not found")

    service = InteractionService(db)
    is_liked, like_count = await service.toggle_like(user.id, paper_id)

    return LikeResponse(
        paper_id=paper_id,
        is_liked=is_liked,
        like_count=like_count,
    )


@router.get("/users/me/likes", response_model=PaginatedLikedPapers)
async def get_my_likes(
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """내가 좋아요한 논문 목록"""
    service = InteractionService(db)
    return await service.get_user_likes(user.id, page, limit)


# ============================================================
# Bookmark
# ============================================================
@router.post("/papers/{paper_id}/bookmark", response_model=BookmarkResponse)
async def toggle_bookmark(
    paper_id: UUID,
    user: CurrentUser,
    body: BookmarkRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """논문 북마크 토글 (북마크 <-> 해제)"""
    result = await db.execute(select(Paper.id).where(Paper.id == paper_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Paper not found")

    service = InteractionService(db)
    collection_id = body.collection_id if body else None
    is_bookmarked, bookmark_id = await service.toggle_bookmark(
        user.id, paper_id, collection_id
    )

    return BookmarkResponse(
        paper_id=paper_id,
        is_bookmarked=is_bookmarked,
        bookmark_id=bookmark_id,
    )


@router.patch("/papers/{paper_id}/bookmark/move", response_model=BookmarkResponse)
async def move_bookmark(
    paper_id: UUID,
    body: BookmarkMoveRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """북마크 컬렉션 이동"""
    service = InteractionService(db)
    moved = await service.move_bookmark(user.id, paper_id, body.collection_id)
    if not moved:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    return BookmarkResponse(
        paper_id=paper_id,
        is_bookmarked=True,
        collection_id=body.collection_id,
    )


@router.get("/users/me/bookmarks", response_model=PaginatedBookmarkedPapers)
async def get_my_bookmarks(
    user: CurrentUser,
    collection_id: UUID | None = Query(None, description="컬렉션 필터"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """내가 북마크한 논문 목록"""
    service = InteractionService(db)
    return await service.get_user_bookmarks(user.id, page, limit, collection_id)


# ============================================================
# Collection
# ============================================================
@router.get("/users/me/collections", response_model=CollectionListResponse)
async def get_my_collections(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """내 컬렉션 목록"""
    service = InteractionService(db)
    collections = await service.get_collections(user.id)

    items = []
    for c in collections:
        count = await service.get_collection_bookmark_count(c.id)
        items.append(
            CollectionResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                is_default=c.is_default,
                sort_order=c.sort_order,
                bookmark_count=count,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    return CollectionListResponse(items=items, total=len(items))


@router.post(
    "/users/me/collections", response_model=CollectionResponse, status_code=201
)
async def create_collection(
    body: CollectionCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """컬렉션 생성"""
    service = InteractionService(db)
    collection = await service.create_collection(user.id, body.name, body.description)

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        is_default=collection.is_default,
        sort_order=collection.sort_order,
        bookmark_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.patch(
    "/users/me/collections/{collection_id}", response_model=CollectionResponse
)
async def update_collection(
    collection_id: UUID,
    body: CollectionUpdate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """컬렉션 수정 (기본 컬렉션 수정 불가)"""
    service = InteractionService(db)
    update_data = body.model_dump(exclude_unset=True)
    collection = await service.update_collection(user.id, collection_id, **update_data)

    if not collection:
        raise HTTPException(
            status_code=404,
            detail="Collection not found or cannot modify default collection",
        )

    count = await service.get_collection_bookmark_count(collection.id)
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        is_default=collection.is_default,
        sort_order=collection.sort_order,
        bookmark_count=count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.delete("/users/me/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """컬렉션 삭제 (기본 컬렉션 삭제 불가, 소속 북마크는 기본으로 이동)"""
    service = InteractionService(db)
    deleted = await service.delete_collection(user.id, collection_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Collection not found or cannot delete default collection",
        )


# ============================================================
# Bulk interaction status (논문 목록용)
# ============================================================
@router.post(
    "/papers/interaction-status", response_model=BulkInteractionStatusResponse
)
async def get_bulk_interaction_status(
    body: BulkInteractionStatusRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """여러 논문의 좋아요/북마크 상태 일괄 조회"""
    service = InteractionService(db)
    statuses_raw = await service.get_bulk_interaction_status(user.id, body.paper_ids)

    statuses = {
        str(pid): PaperInteractionStatus(
            paper_id=pid,
            is_liked=data["is_liked"],
            is_bookmarked=data["is_bookmarked"],
            like_count=data["like_count"],
        )
        for pid, data in statuses_raw.items()
    }

    return BulkInteractionStatusResponse(statuses=statuses)
