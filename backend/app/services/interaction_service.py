"""Like & Bookmark 서비스

좋아요, 북마크, 컬렉션 CRUD 비즈니스 로직
"""

import math
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..models.paper import Paper
from ..models.interaction import PaperLike, BookmarkCollection, PaperBookmark


class InteractionService:
    """좋아요 & 북마크 CRUD 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # Like
    # ============================================================
    async def toggle_like(self, user_id: UUID, paper_id: UUID) -> tuple[bool, int]:
        """좋아요 토글. Returns (is_liked, new_like_count)"""
        existing = await self.db.execute(
            select(PaperLike).where(
                PaperLike.user_id == user_id,
                PaperLike.paper_id == paper_id,
            )
        )
        like = existing.scalar_one_or_none()

        if like:
            # Unlike
            await self.db.delete(like)
            await self.db.execute(
                update(Paper)
                .where(Paper.id == paper_id)
                .values(like_count=Paper.like_count - 1)
            )
            await self.db.commit()
            count = await self._get_like_count(paper_id)
            return False, count
        else:
            # Like
            new_like = PaperLike(user_id=user_id, paper_id=paper_id)
            self.db.add(new_like)
            await self.db.execute(
                update(Paper)
                .where(Paper.id == paper_id)
                .values(like_count=Paper.like_count + 1)
            )
            await self.db.commit()
            count = await self._get_like_count(paper_id)
            return True, count

    async def get_liked_paper_ids(
        self, user_id: UUID, paper_ids: list[UUID]
    ) -> set[UUID]:
        """여러 논문의 좋아요 여부 일괄 확인"""
        if not paper_ids:
            return set()
        result = await self.db.execute(
            select(PaperLike.paper_id).where(
                PaperLike.user_id == user_id,
                PaperLike.paper_id.in_(paper_ids),
            )
        )
        return {row[0] for row in result.all()}

    async def get_user_likes(
        self, user_id: UUID, page: int, limit: int
    ) -> dict:
        """사용자의 좋아요 목록 (페이지네이션)"""
        base_query = (
            select(PaperLike)
            .where(PaperLike.user_id == user_id)
            .join(Paper, Paper.id == PaperLike.paper_id)
        )

        # Total count
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Paginated data
        offset = (page - 1) * limit
        result = await self.db.execute(
            select(PaperLike, Paper)
            .join(Paper, Paper.id == PaperLike.paper_id)
            .where(PaperLike.user_id == user_id)
            .order_by(PaperLike.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()

        items = [
            {
                "paper_id": paper.id,
                "paper_str_id": paper.paper_id,
                "title": paper.title,
                "abstract": paper.abstract,
                "journal": paper.journal,
                "year": paper.year,
                "liked_at": like.created_at,
            }
            for like, paper in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0,
        }

    async def _get_like_count(self, paper_id: UUID) -> int:
        result = await self.db.execute(
            select(Paper.like_count).where(Paper.id == paper_id)
        )
        return result.scalar() or 0

    # ============================================================
    # Bookmark
    # ============================================================
    async def toggle_bookmark(
        self, user_id: UUID, paper_id: UUID, collection_id: UUID | None = None
    ) -> tuple[bool, UUID | None]:
        """북마크 토글. Returns (is_bookmarked, bookmark_id)"""
        existing = await self.db.execute(
            select(PaperBookmark).where(
                PaperBookmark.user_id == user_id,
                PaperBookmark.paper_id == paper_id,
            )
        )
        bookmark = existing.scalar_one_or_none()

        if bookmark:
            # Remove bookmark
            await self.db.delete(bookmark)
            await self.db.commit()
            return False, None
        else:
            # If no collection_id, use default collection
            if not collection_id:
                collection_id = await self._get_or_create_default_collection(user_id)

            new_bookmark = PaperBookmark(
                user_id=user_id,
                paper_id=paper_id,
                collection_id=collection_id,
            )
            self.db.add(new_bookmark)
            await self.db.commit()
            await self.db.refresh(new_bookmark)
            return True, new_bookmark.id

    async def get_bookmarked_paper_ids(
        self, user_id: UUID, paper_ids: list[UUID]
    ) -> set[UUID]:
        """여러 논문의 북마크 여부 일괄 확인"""
        if not paper_ids:
            return set()
        result = await self.db.execute(
            select(PaperBookmark.paper_id).where(
                PaperBookmark.user_id == user_id,
                PaperBookmark.paper_id.in_(paper_ids),
            )
        )
        return {row[0] for row in result.all()}

    async def move_bookmark(
        self, user_id: UUID, paper_id: UUID, collection_id: UUID | None
    ) -> bool:
        """북마크를 다른 컬렉션으로 이동"""
        result = await self.db.execute(
            update(PaperBookmark)
            .where(
                PaperBookmark.user_id == user_id,
                PaperBookmark.paper_id == paper_id,
            )
            .values(collection_id=collection_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def get_user_bookmarks(
        self,
        user_id: UUID,
        page: int,
        limit: int,
        collection_id: UUID | None = None,
    ) -> dict:
        """사용자의 북마크 목록 (페이지네이션, 컬렉션 필터)"""
        base_where = [PaperBookmark.user_id == user_id]
        if collection_id:
            base_where.append(PaperBookmark.collection_id == collection_id)

        # Total count
        count_result = await self.db.execute(
            select(func.count(PaperBookmark.id)).where(*base_where)
        )
        total = count_result.scalar() or 0

        # Paginated data
        offset = (page - 1) * limit
        result = await self.db.execute(
            select(PaperBookmark, Paper, BookmarkCollection.name)
            .join(Paper, Paper.id == PaperBookmark.paper_id)
            .outerjoin(
                BookmarkCollection,
                BookmarkCollection.id == PaperBookmark.collection_id,
            )
            .where(*base_where)
            .order_by(PaperBookmark.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()

        items = [
            {
                "bookmark_id": bookmark.id,
                "paper_id": paper.id,
                "paper_str_id": paper.paper_id,
                "title": paper.title,
                "abstract": paper.abstract,
                "journal": paper.journal,
                "year": paper.year,
                "collection_id": bookmark.collection_id,
                "collection_name": coll_name,
                "bookmarked_at": bookmark.created_at,
            }
            for bookmark, paper, coll_name in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0,
        }

    # ============================================================
    # Collection
    # ============================================================
    async def _get_or_create_default_collection(self, user_id: UUID) -> UUID:
        """기본 컬렉션 조회 또는 생성"""
        result = await self.db.execute(
            select(BookmarkCollection).where(
                BookmarkCollection.user_id == user_id,
                BookmarkCollection.is_default == True,  # noqa: E712
            )
        )
        collection = result.scalar_one_or_none()
        if collection:
            return collection.id

        new_collection = BookmarkCollection(
            user_id=user_id,
            name="All Bookmarks",
            is_default=True,
            sort_order=0,
        )
        self.db.add(new_collection)
        await self.db.commit()
        await self.db.refresh(new_collection)
        return new_collection.id

    async def get_collections(self, user_id: UUID) -> list[BookmarkCollection]:
        """유저의 컬렉션 목록 (기본 컬렉션 자동 생성)"""
        await self._get_or_create_default_collection(user_id)

        result = await self.db.execute(
            select(BookmarkCollection)
            .where(BookmarkCollection.user_id == user_id)
            .order_by(BookmarkCollection.sort_order, BookmarkCollection.created_at)
        )
        return list(result.scalars().all())

    async def create_collection(
        self, user_id: UUID, name: str, description: str | None = None
    ) -> BookmarkCollection:
        """컬렉션 생성"""
        result = await self.db.execute(
            select(func.max(BookmarkCollection.sort_order)).where(
                BookmarkCollection.user_id == user_id
            )
        )
        max_order = result.scalar() or 0

        collection = BookmarkCollection(
            user_id=user_id,
            name=name,
            description=description,
            sort_order=max_order + 1,
        )
        self.db.add(collection)
        await self.db.commit()
        await self.db.refresh(collection)
        return collection

    async def update_collection(
        self, user_id: UUID, collection_id: UUID, **kwargs
    ) -> BookmarkCollection | None:
        """컬렉션 수정 (기본 컬렉션 수정 불가)"""
        result = await self.db.execute(
            select(BookmarkCollection).where(
                BookmarkCollection.id == collection_id,
                BookmarkCollection.user_id == user_id,
                BookmarkCollection.is_default == False,  # noqa: E712
            )
        )
        collection = result.scalar_one_or_none()
        if not collection:
            return None

        for key, value in kwargs.items():
            if value is not None:
                setattr(collection, key, value)

        await self.db.commit()
        await self.db.refresh(collection)
        return collection

    async def delete_collection(self, user_id: UUID, collection_id: UUID) -> bool:
        """컬렉션 삭제 (기본 컬렉션 삭제 불가, 소속 북마크는 기본으로 이동)"""
        result = await self.db.execute(
            select(BookmarkCollection).where(
                BookmarkCollection.id == collection_id,
                BookmarkCollection.user_id == user_id,
                BookmarkCollection.is_default == False,  # noqa: E712
            )
        )
        collection = result.scalar_one_or_none()
        if not collection:
            return False

        # 소속 북마크를 기본 컬렉션으로 이동
        default_id = await self._get_or_create_default_collection(user_id)
        await self.db.execute(
            update(PaperBookmark)
            .where(PaperBookmark.collection_id == collection_id)
            .values(collection_id=default_id)
        )

        await self.db.delete(collection)
        await self.db.commit()
        return True

    async def get_collection_bookmark_count(self, collection_id: UUID) -> int:
        """컬렉션의 북마크 수"""
        result = await self.db.execute(
            select(func.count(PaperBookmark.id)).where(
                PaperBookmark.collection_id == collection_id
            )
        )
        return result.scalar() or 0

    # ============================================================
    # Bulk status
    # ============================================================
    async def get_bulk_interaction_status(
        self, user_id: UUID, paper_ids: list[UUID]
    ) -> dict[UUID, dict]:
        """여러 논문의 좋아요/북마크 상태 일괄 조회"""
        if not paper_ids:
            return {}

        liked_ids = await self.get_liked_paper_ids(user_id, paper_ids)
        bookmarked_ids = await self.get_bookmarked_paper_ids(user_id, paper_ids)

        # Get like counts
        result = await self.db.execute(
            select(Paper.id, Paper.like_count).where(Paper.id.in_(paper_ids))
        )
        like_counts = {row[0]: row[1] for row in result.all()}

        return {
            pid: {
                "is_liked": pid in liked_ids,
                "is_bookmarked": pid in bookmarked_ids,
                "like_count": like_counts.get(pid, 0),
            }
            for pid in paper_ids
        }
