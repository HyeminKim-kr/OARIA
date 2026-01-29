"""Papers API 라우터

논문 검색, 조회 엔드포인트
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models.paper import Paper, PaperAuthor, PaperCitation
from ..schemas.paper import (
    PaperListItem,
    PaperDetail,
    PaginatedResponse,
    PaperStats,
    SectionContentResponse,
    ParagraphResponse,
    PDFUrlResponse,
    CitationItem,
    CitationListResponse,
    CitationStatsResponse,
    DisplayResponse,
    DisplaySectionResponse,
    FigureResponse,
    SimilarPaperItem,
    SimilarPapersResponse,
)
from ..services.weaviate_service import weaviate_service
from ..services.s3_service import s3_service
from ..services.similar_papers_service import similar_papers_service

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
    limit: int = Query(10, ge=1, le=500, description="가져올 개수"),
    year_from: Optional[int] = Query(None, description="시작 연도"),
    year_to: Optional[int] = Query(None, description="종료 연도"),
    db: AsyncSession = Depends(get_db),
):
    """최근 수집된 논문 목록"""
    query = (
        select(Paper)
        .options(selectinload(Paper.authors))
    )

    if year_from:
        query = query.where(Paper.year >= year_from)
    if year_to:
        query = query.where(Paper.year <= year_to)

    query = query.order_by(desc(Paper.created_at)).limit(limit)

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


@router.get("/{paper_id}/display", response_model=DisplayResponse)
async def get_paper_display(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """논문 전체 본문 조회 (display.json)

    논문의 전체 본문을 섹션별로 구분하여 반환합니다.
    PDF가 없는 경우 대체 뷰어용으로 사용합니다.
    """
    import asyncio

    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # S3에서 display.json 가져오기
    display_data = await asyncio.to_thread(s3_service.get_display, paper.paper_id)

    if not display_data:
        raise HTTPException(
            status_code=404,
            detail="Display data not available for this paper"
        )

    # 섹션 변환 (섹션 내 인라인 Figure 포함)
    sections = []
    for sec in display_data.get("sections", []):
        # 섹션 내 Figure 변환
        sec_figures = [
            FigureResponse(
                id=fig.get("id", ""),
                label=fig.get("label", ""),
                caption=fig.get("caption"),
                graphic_href=fig.get("graphic_href", ""),
            )
            for fig in sec.get("figures", [])
        ]
        sections.append(DisplaySectionResponse(
            name=sec.get("name", ""),
            title=sec.get("title", ""),
            paragraphs=sec.get("paragraphs", []),
            figures=sec_figures,
        ))

    # 전체 Figure 목록 (하위 호환용)
    figures = [
        FigureResponse(
            id=fig.get("id", ""),
            label=fig.get("label", ""),
            caption=fig.get("caption"),
            graphic_href=fig.get("graphic_href", ""),
        )
        for fig in display_data.get("figures", [])
    ]

    return DisplayResponse(
        paper_id=paper.paper_id,
        title=paper.title,
        journal=paper.journal,
        year=paper.year,
        sections=sections,
        figures=figures,
        has_pdf=paper.has_pdf or False,
    )


# ============================================================
# PDF 엔드포인트 (string paper_id 버전 - 먼저 정의해야 함)
# ============================================================
@router.get("/by-paper-id/{paper_id:path}/pdf/url", response_model=PDFUrlResponse)
async def get_paper_pdf_url_by_paper_id(
    paper_id: str,
    expires_in: int = Query(3600, ge=300, le=86400, description="URL 만료 시간 (초)"),
    db: AsyncSession = Depends(get_db),
):
    """PDF Presigned URL 조회 (string paper_id로 조회)

    논문의 PDF presigned URL을 반환합니다.
    paper_id는 "pmc:PMC12345678" 형식입니다.
    """
    # 논문 조회 (string paper_id로)
    query = select(Paper).where(Paper.paper_id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if not paper.has_pdf:
        raise HTTPException(status_code=404, detail="PDF not available for this paper")

    # Presigned URL 생성
    import asyncio

    url = await asyncio.to_thread(
        s3_service.get_pdf_presigned_url, paper.paper_id, expires_in
    )

    if not url:
        raise HTTPException(status_code=404, detail="PDF file not found in storage")

    return PDFUrlResponse(
        paper_id=paper.paper_id,
        url=url,
        expires_in=expires_in,
    )


@router.get("/by-paper-id/{paper_id:path}/has-pdf")
async def check_paper_has_pdf(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
):
    """논문 PDF 존재 여부 확인 (string paper_id로 조회)

    paper_id는 "pmc:PMC12345678" 형식입니다.
    """
    query = select(Paper.has_pdf).where(Paper.paper_id == paper_id)
    result = await db.execute(query)
    has_pdf = result.scalar_one_or_none()

    if has_pdf is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    return {"paper_id": paper_id, "has_pdf": has_pdf}


# ============================================================
# PDF 엔드포인트 (UUID 버전)
# ============================================================
@router.get("/{paper_id}/pdf")
async def get_paper_pdf(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """PDF 다운로드 (Presigned URL로 리다이렉트)

    논문의 PDF가 있는 경우 S3 presigned URL로 리다이렉트합니다.
    """
    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if not paper.has_pdf:
        raise HTTPException(status_code=404, detail="PDF not available for this paper")

    # Presigned URL 생성
    import asyncio

    url = await asyncio.to_thread(s3_service.get_pdf_presigned_url, paper.paper_id)

    if not url:
        raise HTTPException(status_code=404, detail="PDF file not found in storage")

    return RedirectResponse(url=url, status_code=302)


@router.get("/{paper_id}/pdf/url", response_model=PDFUrlResponse)
async def get_paper_pdf_url(
    paper_id: UUID,
    expires_in: int = Query(3600, ge=300, le=86400, description="URL 만료 시간 (초)"),
    db: AsyncSession = Depends(get_db),
):
    """PDF Presigned URL 조회

    논문의 PDF presigned URL을 반환합니다.
    프론트엔드에서 PDF 뷰어에 직접 사용할 수 있습니다.
    """
    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if not paper.has_pdf:
        raise HTTPException(status_code=404, detail="PDF not available for this paper")

    # Presigned URL 생성
    import asyncio

    url = await asyncio.to_thread(
        s3_service.get_pdf_presigned_url, paper.paper_id, expires_in
    )

    if not url:
        raise HTTPException(status_code=404, detail="PDF file not found in storage")

    return PDFUrlResponse(
        paper_id=paper.paper_id,
        url=url,
        expires_in=expires_in,
    )


# ============================================================
# Citations/References 엔드포인트
# ============================================================
@router.get("/{paper_id}/citations", response_model=CitationListResponse)
async def get_paper_citations(
    paper_id: UUID,
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    db: AsyncSession = Depends(get_db),
):
    """이 논문을 인용한 논문 목록 (Citations)

    다른 논문들이 이 논문을 인용한 관계를 조회합니다.
    - source_paper_id: 인용한 논문 (citing paper)
    - target_paper_id: 현재 논문 (cited paper)
    """
    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Citations 조회 (이 논문을 target으로 하는 관계)
    base_query = select(PaperCitation).where(
        PaperCitation.target_paper_id == paper.paper_id
    )

    # 전체 개수
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 페이지네이션
    offset = (page - 1) * limit
    citations_query = (
        base_query
        .order_by(desc(PaperCitation.created_at))
        .offset(offset)
        .limit(limit)
    )

    citations_result = await db.execute(citations_query)
    citations = citations_result.scalars().all()

    items = [CitationItem.model_validate(c) for c in citations]

    return CitationListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/{paper_id}/references", response_model=CitationListResponse)
async def get_paper_references(
    paper_id: UUID,
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    db: AsyncSession = Depends(get_db),
):
    """이 논문이 인용한 논문 목록 (References)

    현재 논문이 인용한 다른 논문들의 관계를 조회합니다.
    - source_paper_id: 현재 논문 (citing paper)
    - target_paper_id: 인용된 논문 (cited paper)
    """
    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # References 조회 (이 논문을 source로 하는 관계)
    base_query = select(PaperCitation).where(
        PaperCitation.source_paper_id == paper.paper_id
    )

    # 전체 개수
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 페이지네이션
    offset = (page - 1) * limit
    references_query = (
        base_query
        .order_by(desc(PaperCitation.created_at))
        .offset(offset)
        .limit(limit)
    )

    references_result = await db.execute(references_query)
    references = references_result.scalars().all()

    items = [CitationItem.model_validate(r) for r in references]

    return CitationListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.get("/{paper_id}/citation-stats", response_model=CitationStatsResponse)
async def get_paper_citation_stats(
    paper_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """논문 인용 통계

    논문의 인용 수(citation_count)와 참조 수(reference_count)를 조회합니다.
    """
    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return CitationStatsResponse(
        paper_id=paper.paper_id,
        citation_count=paper.citation_count or 0,
        reference_count=paper.reference_count or 0,
    )


# ============================================================
# Similar Papers 엔드포인트
# ============================================================
@router.get("/{paper_id}/similar", response_model=SimilarPapersResponse)
async def get_similar_papers(
    paper_id: UUID,
    source: str = Query("hybrid", description="추천 소스 (citation, reference, vector, hybrid)"),
    limit: int = Query(20, ge=1, le=50, description="결과 개수"),
    db: AsyncSession = Depends(get_db),
):
    """유사 논문 추천

    4가지 추천 방식을 제공합니다:
    - citation: 이 논문을 인용한 논문 (후속 연구)
    - reference: 이 논문이 인용한 논문 (기반 연구)
    - vector: 벡터 유사도 기반 (내용 유사성)
    - hybrid: 위 3가지 조합 (가장 관련성 높음, 기본값)
    """
    # 논문 조회
    query = select(Paper).where(Paper.id == paper_id)
    result = await db.execute(query)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # 유사 논문 조회
    similar_papers, result_source = await similar_papers_service.get_similar_papers(
        paper_id=paper.paper_id,
        pmcid=paper.pmcid,
        pmid=paper.pmid,
        source=source,
        limit=limit,
    )

    # 응답 변환
    items = [
        SimilarPaperItem(
            pmcid=sp.pmcid,
            pmid=sp.pmid,
            doi=sp.doi,
            title=sp.title,
            journal=sp.journal,
            year=sp.year,
            authors=sp.authors,
            recommendation_type=sp.recommendation_type,
            score=sp.score,
            sources=sp.sources or [],
        )
        for sp in similar_papers
    ]

    return SimilarPapersResponse(
        items=items,
        source=result_source,
        total=len(items),
        paper_id=paper.paper_id,
    )
