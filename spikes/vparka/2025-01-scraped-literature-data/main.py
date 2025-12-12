"""
PubMed/PMC ETL System - FastAPI 메인 서버

이 서버는 PubMed 논문 검색 및 수집 API를 제공합니다.

엔드포인트:
- GET  /api/pubmed/count     - 검색 건수 조회
- POST /api/pubmed/preview   - 미리보기 (처음 N건)
- POST /api/pubmed/crawl/start - 배치 크롤링 시작
- GET  /api/pubmed/crawl/status - 크롤링 상태
- POST /api/pubmed/crawl/stop   - 크롤링 중단

실행:
    uv run uvicorn main:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from models import (
    SearchRequest,
    SearchCountResponse,
    SearchPreviewResponse,
    CrawlStartRequest,
    CrawlStatusResponse,
)
from pubmed_client import PubMedClient
from crawler import crawler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 관리"""
    print("🚀 PubMed ETL Server starting...")
    yield
    print("👋 PubMed ETL Server shutting down...")


app = FastAPI(
    title="PubMed/PMC ETL System",
    description="PubMed 논문 검색 및 수집 자동화 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용, 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """루트 - 프론트엔드 HTML 반환"""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {"message": "PubMed ETL API", "docs": "/docs"}


@app.get("/api/pubmed/count", response_model=SearchCountResponse)
async def get_search_count(
    term: str = Query(..., description="검색 키워드"),
    date_from: str = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: str = Query(None, description="종료일 (YYYY-MM-DD)"),
):
    """
    검색 건수 조회
    
    검색어에 해당하는 총 논문 수와 예상 수집 시간을 반환합니다.
    
    예상 시간 계산:
    - 무료 API: 3 requests/second
    - 1 배치(500건) = 3 requests (search + summary + fetch)
    - 1 배치 처리 시간 ≈ 1초
    - 100만건 = 2,000 배치 ≈ 2,000초 ≈ 33시간
    - 안전 마진(네트워크 지연) 포함 → 약 1.5~2배
    """
    try:
        async with PubMedClient() as client:
            total = await client.get_count(term, date_from, date_to)
            
            # 예상 시간 계산 (배치당 1초 + 안전 마진 50%)
            batches = (total + 499) // 500
            estimated_seconds = batches * 1.5
            estimated_hours = estimated_seconds / 3600
            
            return SearchCountResponse(
                total=total,
                term=term,
                estimated_hours=round(estimated_hours, 2)
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pubmed/preview", response_model=SearchPreviewResponse)
async def preview_search(request: SearchRequest):
    """
    검색 미리보기
    
    검색 결과의 처음 N건을 반환합니다.
    각 논문의 제목, 저자, 초록을 포함합니다.
    """
    try:
        async with PubMedClient() as client:
            papers, total = await client.search_and_fetch(
                term=request.term,
                offset=request.offset,
                limit=request.limit,
                date_from=request.date_from,
                date_to=request.date_to,
            )
            
            return SearchPreviewResponse(
                papers=papers,
                total=total,
                term=request.term,
                offset=request.offset,
                limit=request.limit,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pubmed/crawl/start")
async def start_crawl(request: CrawlStartRequest):
    """
    배치 크롤링 시작
    
    지정된 키워드로 대량 논문 수집을 시작합니다.
    백그라운드에서 실행되며, status API로 진행 상황을 확인할 수 있습니다.
    """
    try:
        job = await crawler.start_crawl(
            term=request.term,
            offset=request.offset,
            limit=request.limit,
            batch_size=request.batch_size,
        )
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "message": f"Crawling started for '{request.term}'"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pubmed/crawl/status")
async def get_crawl_status(job_id: str = Query(..., description="Job ID")):
    """
    크롤링 상태 조회
    
    진행률, 수집된 논문 수, 최근 수집된 논문 목록을 반환합니다.
    """
    status = crawler.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return status


@app.post("/api/pubmed/crawl/stop")
async def stop_crawl(job_id: str = Query(..., description="Job ID")):
    """
    크롤링 중단
    
    진행 중인 크롤링을 중단합니다.
    수집된 데이터는 보존됩니다.
    """
    success = await crawler.stop_crawl(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    return {"status": "stopped", "job_id": job_id}


@app.get("/api/pubmed/papers")
async def get_papers(
    job_id: str = Query(..., description="Job ID"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 논문 수"),
):
    """
    수집된 논문 목록 조회
    
    페이지네이션을 지원합니다.
    """
    papers = crawler.get_all_papers(job_id)
    if not papers:
        raise HTTPException(status_code=404, detail=f"Job not found or no papers: {job_id}")
    
    total = len(papers)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    
    return {
        "papers": papers[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }


# Static files for frontend
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
