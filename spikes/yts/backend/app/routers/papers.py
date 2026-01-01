"""Papers API 라우터

논문 검색, 조회 엔드포인트
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.paper import Paper, PaperAuthor
from ..schemas.paper import (
    PaperListItem,
    PaperDetail,
    PaginatedResponse,
    PaperStats,
    SectionContentResponse,
    ParagraphResponse,
)
from ..services.weaviate_service import weaviate_service
from ..services.s3_service import s3_service

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/search", response_model=PaginatedResponse)
async def search_papers(
    q: Optional[str] = Query(None, description="검색어 (제목, 초록)"),
    year_from: Optional[int] = Query(None, description="시작 연도"),
    year_to: Optional[int] = Query(None, description="종료 연도"),
    keyword: Optional[str] = Query(None, description="키워드 필터"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    db: AsyncSession = Depends(get_db),
):
    """논문 검색

    - q: 제목 또는 초록에서 검색 (ILIKE)
    - year_from/year_to: 연도 범위 필터
    - keyword: 키워드 배열에서 검색
    """
    # 기본 쿼리
    query = select(Paper).options(selectinload(Paper.authors))

    # 검색어 필터
    if q:
        search_term = f"%{q}%"
        query = query.where(
            or_(
                Paper.title.ilike(search_term),
                Paper.abstract.ilike(search_term),
            )
        )

    # 연도 필터
    if year_from:
        query = query.where(Paper.year >= year_from)
    if year_to:
        query = query.where(Paper.year <= year_to)

    # 키워드 필터
    if keyword:
        query = query.where(Paper.keywords.any(keyword))

    # 전체 개수 조회
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 정렬 및 페이지네이션
    offset = (page - 1) * limit
    query = query.order_by(desc(Paper.created_at)).offset(offset).limit(limit)

    # 실행
    result = await db.execute(query)
    papers = result.scalars().unique().all()

    # 응답 변환
    items = [PaperListItem.model_validate(paper) for paper in papers]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.get("/recent", response_model=list[PaperListItem])
async def get_recent_papers(
    limit: int = Query(10, ge=1, le=50, description="가져올 개수"),
    db: AsyncSession = Depends(get_db),
):
    """최근 수집된 논문 목록"""
    query = (
        select(Paper)
        .options(selectinload(Paper.authors))
        .order_by(desc(Paper.created_at))
        .limit(limit)
    )

    result = await db.execute(query)
    papers = result.scalars().unique().all()

    return [PaperListItem.model_validate(paper) for paper in papers]


@router.get("/stats", response_model=PaperStats)
async def get_paper_stats(db: AsyncSession = Depends(get_db)):
    """논문 통계"""
    # 전체 개수
    total_result = await db.execute(select(func.count(Paper.id)))
    total = total_result.scalar() or 0

    # 연도별 통계
    year_query = (
        select(Paper.year, func.count(Paper.id).label("count"))
        .where(Paper.year.isnot(None))
        .group_by(Paper.year)
        .order_by(desc(Paper.year))
        .limit(10)
    )
    year_result = await db.execute(year_query)
    by_year = [{"year": row.year, "count": row.count} for row in year_result]

    # 최근 7일 수집 개수
    from datetime import datetime, timedelta

    week_ago = datetime.now() - timedelta(days=7)
    recent_query = select(func.count(Paper.id)).where(Paper.created_at >= week_ago)
    recent_result = await db.execute(recent_query)
    recent_count = recent_result.scalar() or 0

    return PaperStats(
        total=total,
        by_year=by_year,
        recent_count=recent_count,
    )


@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """논문 상세 조회"""
    query = (
        select(Paper)
        .options(selectinload(Paper.authors))
        .where(Paper.id == paper_id)
    )

    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return PaperDetail.model_validate(paper)


@router.get("/{paper_id}/sections/{section}", response_model=SectionContentResponse)
async def get_section_content(
    paper_id: str,
    section: str,
):
    """논문 섹션 내용 조회 (display.json 사용)

    Reference 클릭 시 모달에 표시
    단락별로 구분된 데이터 반환
    """
    import asyncio

    # Weaviate에서 메타데이터 가져오기 (title, journal, year, 섹션 오프셋)
    chunks = await asyncio.to_thread(
        weaviate_service.get_chunks_by_paper_and_section,
        paper_id,
        section,
    )

    first_chunk = chunks[0] if chunks else {}
    section_fulltext_offset = int(first_chunk.get("offsetStart", 0))

    # S3에서 display.json 가져오기
    display_data = await asyncio.to_thread(s3_service.get_display, paper_id)

    if display_data:
        # display.json에서 해당 섹션 찾기
        section_data = _find_section_in_display(display_data, section)

        if section_data:
            raw_paragraphs = section_data.get("paragraphs", [])

            # 문단별 오프셋 계산 (Batch parser와 동일하게 공백으로 연결)
            paragraph_responses = []
            current_offset = 0

            for p in raw_paragraphs:
                text = p.get("text", "")
                paragraph_responses.append(
                    ParagraphResponse(
                        text=text,
                        offset_start=current_offset,
                        offset_end=current_offset + len(text),
                    )
                )
                current_offset += len(text) + 1  # +1 for space separator

            total_text = " ".join(p.get("text", "") for p in raw_paragraphs)

            return SectionContentResponse(
                paper_id=paper_id,
                section=section,
                section_title=section_data.get("title", section.title()),
                title=first_chunk.get("title", ""),
                journal=first_chunk.get("journal"),
                year=first_chunk.get("year"),
                paragraphs=paragraph_responses,
                total_text=total_text,
                section_fulltext_offset=section_fulltext_offset,
            )

    # display.json 없으면 404
    raise HTTPException(status_code=404, detail="Section not found (display.json missing)")


def _find_section_in_display(display_data: dict, section_name: str) -> dict | None:
    """display.json에서 섹션 찾기"""
    sections = display_data.get("sections", [])

    for sec in sections:
        if sec.get("name") == section_name:
            return sec

    return None
