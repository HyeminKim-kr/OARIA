"""
OARIA Literature - FastAPI 메인 서버

PubMed ETL, 임베딩, 의미 검색 API를 제공합니다.

엔드포인트:
- GET  /api/health          - 헬스체크
- GET  /api/pubmed/count    - 검색 건수
- POST /api/etl/start       - ETL 시작
- GET  /api/etl/status      - ETL 상태
- POST /api/search/semantic - 의미 검색
- GET  /api/papers          - 저장된 논문 목록
- GET  /api/embedding/status - 임베딩 상태

실행:
    uvicorn src.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from .config import settings
from .db import get_db, init_db
from .models import (
    Paper,
    PaperResponse,
    SearchRequest,
    SearchCountResponse,
    ETLStartRequest,
    ETLStatusResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
    EmbeddingStatusResponse,
)
from .pubmed_client import PubMedClient
from .etl_worker import etl_worker
from .embedding_worker import embedding_worker
from .qdrant_client import get_qdrant_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 관리"""
    print(f"🚀 OARIA Literature Server starting... (mode: {settings.mode})")
    
    # DB 테이블 생성
    init_db()
    
    # 임베딩 워커 시작 (선택사항)
    # await embedding_worker.start()
    
    yield
    
    # 정리
    await embedding_worker.stop()
    print("👋 OARIA Literature Server shutting down...")


app = FastAPI(
    title="OARIA Literature - PubMed ETL",
    description="PubMed/PMC ETL → SQL → Embedding → Qdrant 파이프라인",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health Check
# =============================================================================

@app.get("/api/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "mode": settings.mode,
        "storage": settings.storage_backend,
    }


# =============================================================================
# PubMed Search
# =============================================================================

@app.get("/api/pubmed/count")
async def get_pubmed_count(
    term: str = Query(..., description="검색 키워드"),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
):
    """PubMed 검색 건수 조회"""
    try:
        async with PubMedClient() as client:
            total = await client.get_count(term, date_from, date_to)
            
            # 예상 시간 계산
            batches = (total + 499) // 500
            estimated_hours = (batches * 1.5) / 3600
            
            return {
                "total": total,
                "term": term,
                "estimated_hours": round(estimated_hours, 2),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pubmed/preview")
async def preview_pubmed(request: SearchRequest):
    """PubMed 검색 미리보기"""
    try:
        async with PubMedClient() as client:
            papers, total = await client.search_and_fetch(
                term=request.term,
                limit=20,
                date_from=request.date_from,
                date_to=request.date_to,
            )
            
            return {
                "papers": papers,
                "total": total,
                "term": request.term,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ETL
# =============================================================================

@app.post("/api/etl/start")
async def start_etl(request: ETLStartRequest):
    """ETL 시작"""
    try:
        job = await etl_worker.start_etl(
            term=request.term,
            limit=request.limit,
            offset=request.offset,
        )
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "message": f"ETL started for '{request.term}'",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etl/status")
async def get_etl_status(job_id: str = Query(..., description="Job ID")):
    """ETL 상태 조회"""
    status = etl_worker.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return status


@app.post("/api/etl/stop")
async def stop_etl(job_id: str = Query(..., description="Job ID")):
    """ETL 중단"""
    success = await etl_worker.stop_etl(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"status": "stopped", "job_id": job_id}


# =============================================================================
# Papers (DB)
# =============================================================================

@app.get("/api/papers")
async def get_papers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """저장된 논문 목록 조회"""
    from .models.paper import Paper as PaperModel
    
    total = db.query(func.count(PaperModel.pmid)).scalar()
    
    papers = (
        db.query(PaperModel)
        .order_by(PaperModel.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    return {
        "papers": [
            {
                "pmid": p.pmid,
                "title": p.title,
                "abstract": p.abstract[:300] + "..." if len(p.abstract) > 300 else p.abstract,
                "authors": p.authors,
                "journal": p.journal,
                "pubdate": p.pubdate,
                "embedding_status": p.embedding_status,
            }
            for p in papers
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
    }


@app.get("/api/papers/{pmid}")
async def get_paper(pmid: str, db: Session = Depends(get_db)):
    """논문 상세 조회"""
    from .models.paper import Paper as PaperModel
    
    paper = db.query(PaperModel).filter(PaperModel.pmid == pmid).first()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper not found: {pmid}")
    
    return {
        "pmid": paper.pmid,
        "pmcid": paper.pmcid,
        "title": paper.title,
        "abstract": paper.abstract,
        "authors": paper.authors,
        "journal": paper.journal,
        "pubdate": paper.pubdate,
        "doi": paper.doi,
        "mesh_terms": paper.mesh_terms,
        "fulltext_path": paper.fulltext_path,
        "embedding_status": paper.embedding_status,
        "created_at": paper.created_at,
    }


# =============================================================================
# Semantic Search
# =============================================================================

@app.post("/api/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(request: SemanticSearchRequest, db: Session = Depends(get_db)):
    """의미 검색 (Qdrant)"""
    from .models.paper import Paper as PaperModel
    
    try:
        # 쿼리 임베딩 생성
        query_embedding = embedding_worker.encode(request.query)
        
        # Qdrant 검색
        qdrant = get_qdrant_client()
        results = qdrant.search(
            query_embedding=query_embedding,
            limit=request.limit,
            score_threshold=request.score_threshold,
        )
        
        # DB에서 추가 정보 가져오기
        pmids = [r["pmid"] for r in results]
        papers = db.query(PaperModel).filter(PaperModel.pmid.in_(pmids)).all()
        paper_map = {p.pmid: p for p in papers}
        
        # 결과 조합
        search_results = []
        for r in results:
            paper = paper_map.get(r["pmid"])
            if paper:
                search_results.append(SemanticSearchResult(
                    pmid=paper.pmid,
                    title=paper.title,
                    abstract=paper.abstract,
                    score=r["score"],
                    authors=paper.authors or [],
                    journal=paper.journal,
                    pubdate=paper.pubdate,
                ))
        
        return SemanticSearchResponse(
            query=request.query,
            results=search_results,
            total=len(search_results),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Embedding Status
# =============================================================================

@app.get("/api/embedding/status", response_model=EmbeddingStatusResponse)
async def get_embedding_status():
    """임베딩 처리 상태"""
    return embedding_worker.get_status()


@app.post("/api/embedding/process")
async def process_embeddings(batch_size: int = Query(10, ge=1, le=100)):
    """임베딩 수동 처리"""
    try:
        processed = await embedding_worker.process_pending_tasks(batch_size)
        return {"processed": processed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/embedding/worker/start")
async def start_embedding_worker():
    """임베딩 워커 시작"""
    await embedding_worker.start()
    return {"status": "started"}


@app.post("/api/embedding/worker/stop")
async def stop_embedding_worker():
    """임베딩 워커 중단"""
    await embedding_worker.stop()
    return {"status": "stopped"}


# =============================================================================
# Database Management
# =============================================================================

@app.post("/api/db/init")
async def init_database():
    """데이터베이스 테이블 초기화 (없으면 생성)"""
    try:
        init_db()
        return {"status": "success", "message": "Database tables initialized"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/db/reset")
async def reset_database(confirm: str = Query(..., description="확인용: 'yes'를 입력")):
    """
    데이터베이스 초기화 (모든 데이터 삭제)
    
    ⚠️ 주의: 모든 논문과 임베딩 데이터가 삭제됩니다!
    """
    if confirm != "yes":
        raise HTTPException(status_code=400, detail="reset을 확인하려면 confirm=yes 를 입력하세요")
    
    try:
        from .db import engine, Base
        from .models.paper import Paper as PaperModel, EmbeddingTask
        
        # 테이블 삭제 후 재생성
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # Qdrant 컬렉션도 재생성
        qdrant = get_qdrant_client()
        try:
            qdrant._get_client().delete_collection(qdrant.collection)
        except Exception:
            pass
        qdrant._initialized = False
        qdrant.ensure_collection()
        
        return {
            "status": "success",
            "message": "Database and Qdrant collection reset successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/stats")
async def get_db_stats(db: Session = Depends(get_db)):
    """데이터베이스 통계"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    
    paper_count = db.query(func.count(PaperModel.pmid)).scalar()
    
    # 임베딩 상태별 카운트
    pending = db.query(func.count(EmbeddingTask.id)).filter(
        EmbeddingTask.status == "pending"
    ).scalar()
    done = db.query(func.count(EmbeddingTask.id)).filter(
        EmbeddingTask.status == "done"
    ).scalar()
    error = db.query(func.count(EmbeddingTask.id)).filter(
        EmbeddingTask.status == "error"
    ).scalar()
    
    # Qdrant 포인트 수
    try:
        qdrant = get_qdrant_client()
        qdrant_count = qdrant.get_count()
    except Exception:
        qdrant_count = 0
    
    return {
        "papers": paper_count,
        "embeddings": {
            "pending": pending,
            "done": done,
            "error": error,
            "total": pending + done + error,
        },
        "qdrant_points": qdrant_count,
    }


# =============================================================================
# Logging
# =============================================================================

from collections import deque
from datetime import datetime

# 로그 버퍼 (최대 500개 보관)
log_buffer: deque = deque(maxlen=500)


def add_log(message: str, level: str = "info"):
    """로그 추가"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    log_buffer.append(log_entry)
    # 콘솔에도 출력
    icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
    print(f"{icon} [{level.upper()}] {message}")


@app.get("/api/logs")
async def get_logs(limit: int = Query(100, ge=1, le=500)):
    """최근 로그 조회"""
    logs = list(log_buffer)[-limit:]
    return {"logs": logs, "total": len(log_buffer)}


@app.post("/api/logs/clear")
async def clear_logs():
    """로그 초기화"""
    log_buffer.clear()
    add_log("로그가 초기화되었습니다", "info")
    return {"status": "cleared"}


# 기존 ETL 시작에 로그 추가
original_start_etl = start_etl


@app.post("/api/etl/start", include_in_schema=False)
async def start_etl_with_log(request: ETLStartRequest):
    add_log(f"ETL 시작: '{request.term}' (offset={request.offset}, limit={request.limit})", "info")
    try:
        result = await original_start_etl(request)
        add_log(f"ETL 작업 생성됨: {result['job_id']}", "success")
        return result
    except Exception as e:
        add_log(f"ETL 시작 실패: {str(e)}", "error")
        raise

