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
from pydantic import BaseModel
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
from .etl_worker import etl_worker, add_log, get_logs, clear_logs
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
async def health_check(db: Session = Depends(get_db)):
    """헬스체크 (DB 연결 상태 포함)"""
    from .db import get_available_modes, get_custom_connection_info
    from .config import get_active_mode
    
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        print(f"⚠️ Health check DB execute failed: {e}")
    
    modes_info = get_available_modes()
    active_mode = get_active_mode()
    
    # 커스텀 연결 정보
    custom_info = get_custom_connection_info() if active_mode == "custom" else {}
    
    # modes_info에서 실제 연결 상태/타입 확인
    if active_mode == "custom" and custom_info:
        db_type = custom_info.get("db_type", "postgresql")
        db_connected = True  # 커스텀 연결 시 연결 성공으로 가정
    elif active_mode in modes_info.get("modes", {}):
        mode_info = modes_info["modes"][active_mode]
        if not db_connected and mode_info.get("connected"):
            db_connected = True
        db_type = mode_info.get("db_type", settings.db_type)
    else:
        db_type = settings.db_type
    
    response = {
        "status": "healthy",
        "mode": active_mode,
        "db_type": db_type,
        "db_connected": db_connected,
        "storage": settings.storage_backend,
        "supports_switching": modes_info.get("supports_switching", False),
    }
    
    # 커스텀 연결 시 추가 정보
    if active_mode == "custom" and custom_info:
        response["custom_connection"] = {
            "host": custom_info.get("host"),
            "port": custom_info.get("port"),
            "database": custom_info.get("database"),
            "connected_at": custom_info.get("connected_at"),
        }
    
    return response


@app.get("/api/db/modes")
async def get_db_modes():
    """사용 가능한 DB 모드 목록"""
    from .db import get_available_modes
    return get_available_modes()


@app.post("/api/db/switch")
async def switch_db_mode(mode: str = Query(..., description="local 또는 gcp")):
    """런타임에 DB 모드 전환"""
    from .db import switch_database
    
    if mode not in ["local", "gcp"]:
        raise HTTPException(status_code=400, detail="Mode must be 'local' or 'gcp'")
    
    result = switch_database(mode)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Switch failed"))
    
    add_log("db", f"🔄 DB Mode 전환: {result['old_mode']} → {result['new_mode']}")
    
    return result


class CustomDBConnectionRequest(BaseModel):
    """커스텀 DB 연결 요청"""
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    db_type: str = "postgresql"  # postgresql 또는 mysql
    test_only: bool = False  # True면 테스트만, False면 연결 전환


@app.post("/api/db/connect-custom")
async def connect_custom_db(request: CustomDBConnectionRequest):
    """커스텀 DB에 연결 (테스트 또는 전환)"""
    from .db import connect_custom_database
    from urllib.parse import quote_plus
    import os
    
    # URL 인코딩 (특수문자 @ : / 등 처리)
    username_enc = quote_plus(request.username)
    password_enc = quote_plus(request.password) if request.password else ''
    
    # Docker 환경에서 localhost/127.0.0.1 → host.docker.internal 변환
    host = request.host
    if host in ('localhost', '127.0.0.1') and os.path.exists('/.dockerenv'):
        host = 'host.docker.internal'
        add_log("db", f"🐳 Docker 환경 감지: {request.host} → {host}")
    
    # URL 생성
    if request.db_type == "mysql":
        url = f"mysql+pymysql://{username_enc}:{password_enc}@{host}:{request.port}/{request.database}"
    else:
        url = f"postgresql://{username_enc}:{password_enc}@{host}:{request.port}/{request.database}"
    
    result = connect_custom_database(
        url=url,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        database=request.database,
        test_only=request.test_only
    )
    
    if result["success"]:
        if request.test_only:
            add_log("db", f"✅ 커스텀 DB 연결 테스트 성공: {request.host}:{request.port}/{request.database}")
        else:
            add_log("success", f"🔗 커스텀 DB 연결 완료: {request.host}:{request.port}")
    else:
        add_log("error", f"커스텀 DB 연결 실패: {result.get('error', 'Unknown error')}")
        raise HTTPException(status_code=500, detail=result.get("error", "Connection failed"))
    
    return result


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


@app.get("/api/etl/keyword-stats")
async def get_keyword_stats(
    term: str = Query(..., description="Search term"),
    db: Session = Depends(get_db),
):
    """키워드별 수집 통계 조회 (Resume 지원용)"""
    from .models.paper import Paper as PaperModel
    
    # 해당 키워드로 검색된 논문 수 (간단히 term이 abstract에 포함된 것으로 추정)
    # 실제로는 search_term 필드를 Paper 모델에 추가하는 것이 더 정확함
    search_term = f"%{term}%"
    collected = db.query(PaperModel).filter(
        (PaperModel.title.ilike(search_term)) |
        (PaperModel.abstract.ilike(search_term))
    ).count()
    
    # PubMed 전체 결과 수 조회
    try:
        pubmed_client = PubMedClient()
        pubmed_total = await pubmed_client.get_count(term)
    except:
        pubmed_total = 0
    
    return {
        "term": term,
        "collected": collected,
        "pubmed_total": pubmed_total,
        "last_offset": collected,  # 다음 offset = 현재까지 수집된 수
    }


def to_kst_korean(dt):
    """UTC datetime을 한국식 KST 포맷으로 변환 (YYYY. MM. DD AM/PM HH:mm:ss)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kst_dt = dt.astimezone(KST)
    
    hour = kst_dt.hour
    am_pm = "AM" if hour < 12 else "PM"
    
    return kst_dt.strftime(f"%Y. %m. %d {am_pm} %H:%M:%S")


@app.get("/api/etl/search")
async def search_keyword_stats(
    term: str = Query(..., description="Search term"),
    db: Session = Depends(get_db),
):
    """키워드 기반 진행률 통계 조회 (Progress %, Remaining, Resume Index)"""
    from .models.cron_log import CronLog
    from .models.paper import Paper as PaperModel
    
    # PubMed 전체 수 조회 (async with으로 클라이언트 생성)
    pubmed_total = 0
    try:
        async with PubMedClient() as client:
            pubmed_total = await client.get_count(term)
    except Exception as e:
        add_log("warning", f"PubMed count 조회 실패: {e}")
        pubmed_total = 0
    
    # DB에 저장된 해당 키워드 논문 수
    db_count = db.query(PaperModel).filter(
        (PaperModel.title.ilike(f"%{term}%")) |
        (PaperModel.abstract.ilike(f"%{term}%"))
    ).count()

    
    # CronLog에서 해당 키워드 최근 기록
    recent_logs = db.query(CronLog).filter(
        CronLog.keyword.ilike(f"%{term}%")
    ).order_by(CronLog.run_at.desc()).limit(20).all()
    
    # 마지막 처리 인덱스 (resume point)
    last_pmid = None
    last_run_dt = None
    total_fetched = 0
    total_inserted = 0
    total_skipped = 0
    
    if recent_logs:
        last_log = recent_logs[0]
        last_pmid = last_log.pmid_range_end
        last_run_dt = last_log.run_at
        
        for log in recent_logs:
            total_fetched += log.fetched or 0
            total_inserted += log.inserted or 0
            total_skipped += log.skipped or 0
    
    # Progress 계산
    progress = 0.0
    remaining = pubmed_total
    
    if pubmed_total > 0:
        progress = min((db_count / pubmed_total) * 100, 100)
        remaining = max(pubmed_total - db_count, 0)
    
    # Resume Index 계산 (DB의 마지막 offset)
    resume_index = db_count
    
    # ETA 추정 (배치당 평균 시간 기반)
    # 배치 사이즈 200, 배치당 약 5초 가정
    eta_display = None
    eta_minutes = None
    if remaining > 0:
        batches_needed = remaining / 200  # 배치 수
        seconds_per_batch = 5  # 배치당 5초
        total_seconds = int(batches_needed * seconds_per_batch)
        eta_minutes = total_seconds // 60
        
        # 사람이 읽기 쉬운 형식으로 변환
        if total_seconds < 60:
            eta_display = f"{total_seconds}s"
        elif total_seconds < 3600:
            eta_display = f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            mins = (total_seconds % 3600) // 60
            eta_display = f"{hours}h {mins}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            eta_display = f"{days}d {hours}h"
    
    add_log("info", f"🔍 Search: term=\"{term}\" → Progress {progress:.1f}% | Remaining {remaining:,}")
    
    return {
        "term": term,
        "pubmed_total": pubmed_total,
        "fetched": db_count,
        "remaining": remaining,
        "progress": round(progress, 1),
        "resume_index": resume_index,
        "last_pmid": last_pmid,
        "last_sync_kst": to_kst_korean(last_run_dt),
        "total_runs": len(recent_logs),
        "total_inserted": total_inserted,
        "total_skipped": total_skipped,
        "eta_minutes": eta_minutes,
        "eta_display": eta_display,

    }



# Auto ETL 상태 관리
auto_etl_state = {
    "running": False,
    "paused": False,
    "term": "",
    "batch_size": 100,
    "current_job_id": None,
    "current_offset": 0,
    "total_batches": 0,
    "completed_batches": 0,
}
auto_etl_task = None  # Background task for auto ETL loop


async def auto_etl_loop():
    """Auto ETL 루프 - 배치를 연속으로 실행"""
    global auto_etl_state
    
    while auto_etl_state["running"]:
        # 일시정지 상태면 대기
        if auto_etl_state["paused"]:
            await asyncio.sleep(1)
            continue
        
        try:
            # 현재 offset에서 배치 시작
            term = auto_etl_state["term"]
            batch_size = auto_etl_state["batch_size"]
            offset = auto_etl_state["current_offset"]
            
            add_log("etl", f"🔄 Auto ETL Batch #{auto_etl_state['completed_batches'] + 1} starting (offset={offset})")
            
            job = await etl_worker.start_etl(
                term=term,
                limit=batch_size,
                offset=offset,
            )
            auto_etl_state["current_job_id"] = job.job_id
            auto_etl_state["total_batches"] += 1
            
            # 작업 완료 대기
            while True:
                status = etl_worker.get_status(job.job_id)
                if not status:
                    break
                
                if status["status"] in ["completed", "error", "stopped"]:
                    # 배치 완료
                    auto_etl_state["completed_batches"] += 1
                    auto_etl_state["current_offset"] = offset + batch_size
                    
                    if status["status"] == "completed":
                        add_log("success", f"✅ Auto ETL Batch #{auto_etl_state['completed_batches']} Completed == Inserted: +{status['inserted']} | Skipped: {status['skipped']}")
                    elif status["status"] == "error":
                        add_log("error", f"❌ Auto ETL Batch #{auto_etl_state['completed_batches']} Error: {status['message']}")
                    elif status["status"] == "stopped":
                        add_log("warning", f"⏹️ Auto ETL Batch #{auto_etl_state['completed_batches']} Stopped")
                        auto_etl_state["running"] = False
                    break
                
                await asyncio.sleep(1)
                
                # 일시정지/취소 체크
                if not auto_etl_state["running"]:
                    break
                if auto_etl_state["paused"]:
                    add_log("etl", f"⏸️ Auto ETL Paused during batch #{auto_etl_state['completed_batches'] + 1}")
                    break
            
            # 취소되었으면 루프 종료
            if not auto_etl_state["running"]:
                break
            
            # 다음 배치 전 짧은 대기
            await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            add_log("warning", "⏹️ Auto ETL Loop Cancelled")
            break
        except Exception as e:
            add_log("error", f"❌ Auto ETL Loop Error: {e}")
            await asyncio.sleep(5)  # 에러 시 5초 대기 후 재시도
    
    add_log("info", f"🏁 Auto ETL Loop Ended (Completed {auto_etl_state['completed_batches']} batches)")


@app.post("/api/etl/auto/start")
async def start_auto_etl(
    term: str = Query(...),
    batch_size: int = Query(100, ge=10, le=500),
):
    """Auto ETL 시작 - 연속적으로 배치 실행"""
    global auto_etl_state, auto_etl_task
    
    if auto_etl_state["running"] and not auto_etl_state["paused"]:
        raise HTTPException(status_code=400, detail="Auto ETL already running")
    
    auto_etl_state["running"] = True
    auto_etl_state["paused"] = False
    auto_etl_state["term"] = term
    auto_etl_state["batch_size"] = batch_size
    auto_etl_state["current_offset"] = 0
    auto_etl_state["total_batches"] = 0
    auto_etl_state["completed_batches"] = 0
    
    add_log("etl", f"🟢 Auto ETL Started (term=\"{term}\", batch={batch_size})")
    
    # Start background auto ETL loop
    auto_etl_task = asyncio.create_task(auto_etl_loop())
    
    return {
        "status": "started",
        "term": term,
        "batch_size": batch_size,
    }


@app.post("/api/etl/auto/pause")
async def pause_auto_etl():
    """Auto ETL 일시정지"""
    global auto_etl_state
    
    if not auto_etl_state["running"]:
        raise HTTPException(status_code=400, detail="Auto ETL not running")
    
    auto_etl_state["paused"] = True
    add_log("etl", "🔴 Auto ETL Paused")
    
    return {"status": "paused"}


@app.post("/api/etl/auto/resume")
async def resume_auto_etl():
    """Auto ETL 재개"""
    global auto_etl_state, auto_etl_task
    
    if not auto_etl_state["running"]:
        raise HTTPException(status_code=400, detail="Auto ETL not running")
    
    auto_etl_state["paused"] = False
    add_log("etl", "🟡 Auto ETL Resumed")
    
    # 루프가 중단되었으면 다시 시작
    if auto_etl_task is None or auto_etl_task.done():
        auto_etl_task = asyncio.create_task(auto_etl_loop())
    
    return {"status": "resumed"}


@app.post("/api/etl/auto/cancel")
async def cancel_auto_etl():
    """Auto ETL 완전 취소"""
    global auto_etl_state, auto_etl_task
    
    # 현재 작업 중지
    if auto_etl_state["current_job_id"]:
        await etl_worker.stop_etl(auto_etl_state["current_job_id"])
    
    # 백그라운드 태스크 취소
    if auto_etl_task and not auto_etl_task.done():
        auto_etl_task.cancel()
        try:
            await auto_etl_task
        except asyncio.CancelledError:
            pass
    
    auto_etl_state["running"] = False
    auto_etl_state["paused"] = False
    auto_etl_state["current_job_id"] = None
    auto_etl_task = None
    
    add_log("etl", "⏹️ Auto ETL Cancelled")
    
    return {"status": "cancelled"}


@app.get("/api/etl/auto/status")
async def get_auto_etl_status():
    """Auto ETL 상태 조회"""
    return {
        "running": auto_etl_state["running"],
        "paused": auto_etl_state["paused"],
        "term": auto_etl_state["term"],
        "batch_size": auto_etl_state["batch_size"],
        "current_job_id": auto_etl_state["current_job_id"],
        "current_offset": auto_etl_state["current_offset"],
        "total_batches": auto_etl_state["total_batches"],
        "completed_batches": auto_etl_state["completed_batches"],
    }


# Realtime Pull 상태
realtime_pull_state = {
    "enabled": False,
    "term": "",
    "interval_seconds": 60,
}


@app.post("/api/etl/realtime/start")
async def start_realtime_pull(
    term: str = Query(...),
    interval_seconds: int = Query(60, ge=30, le=300),
):
    """실시간 배치 Pull 시작 (1분 간격)"""
    global realtime_pull_state
    
    realtime_pull_state["enabled"] = True
    realtime_pull_state["term"] = term
    realtime_pull_state["interval_seconds"] = interval_seconds
    
    add_log("etl", f"⏱️ Real-time Pull Started (term=\"{term}\", interval={interval_seconds}s)")
    
    return {
        "status": "started",
        "term": term,
        "interval_seconds": interval_seconds,
    }


@app.post("/api/etl/realtime/stop")
async def stop_realtime_pull():
    """실시간 배치 Pull 중지"""
    global realtime_pull_state
    
    realtime_pull_state["enabled"] = False
    add_log("etl", "⏹️ Real-time Pull Stopped")
    
    return {"status": "stopped"}


@app.get("/api/etl/realtime/status")
async def get_realtime_pull_status():
    """실시간 배치 Pull 상태"""
    return realtime_pull_state


# Papers (DB)
# =============================================================================

@app.get("/api/papers")
async def get_papers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search term for title/abstract"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db),
):
    """저장된 논문 목록 조회 (검색, 정렬 지원)"""
    from .models.paper import Paper as PaperModel
    
    query = db.query(PaperModel)
    
    # 검색
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (PaperModel.title.ilike(search_term)) |
            (PaperModel.abstract.ilike(search_term)) |
            (PaperModel.pmid.ilike(search_term))
        )
    
    total = query.count()
    
    # 정렬
    sort_column = getattr(PaperModel, sort, PaperModel.created_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    papers = query.offset((page - 1) * per_page).limit(per_page).all()
    
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
                "created_at": str(p.created_at) if p.created_at else None,
            }
            for p in papers
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }


from pydantic import BaseModel

class DeleteAllRequest(BaseModel):
    confirm: str

@app.delete("/api/papers/all")
async def delete_all_papers(request: DeleteAllRequest, db: Session = Depends(get_db)):
    """전체 논문 삭제 (확인 필요)"""
    from .models.paper import Paper as PaperModel
    
    if request.confirm != "DELETE":
        raise HTTPException(status_code=400, detail="Confirmation required: type 'DELETE'")
    
    count = db.query(PaperModel).count()
    db.query(PaperModel).delete()
    db.commit()
    
    # 로그 추가
    from .etl_worker import etl_worker
    await etl_worker.add_log("warning", f"Deleted all {count} papers from database")
    
    return {"deleted": count, "message": f"Deleted {count} papers"}


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
# Logging (전역 콘솔 + SSE 스트림)
# =============================================================================

from fastapi.responses import StreamingResponse
import asyncio


@app.get("/api/logs")
async def get_logs_api(limit: int = Query(100, ge=1, le=1000)):
    """최근 로그 조회 (전역 콘솔용)"""
    logs = get_logs(limit)
    return {"logs": logs, "total": len(logs)}


class AddLogRequest(BaseModel):
    level: str = "info"
    message: str


@app.post("/api/logs/add")
async def add_log_api(request: AddLogRequest):
    """프론트엔드에서 로그 추가 (System Console 표시용)"""
    add_log(request.level, request.message)
    return {"success": True}


@app.get("/api/console/stream")
async def console_sse_stream():
    """전역 콘솔 SSE 스트림"""
    
    async def event_generator():
        last_count = 0
        while True:
            logs = get_logs(50)
            current_count = len(logs)
            
            # 새 로그가 있으면 전송
            if current_count > last_count:
                new_logs = logs[-(current_count - last_count):]
                for log in new_logs:
                    import json
                    yield f"data: {json.dumps(log)}\n\n"
                last_count = current_count
            elif current_count < last_count:
                # 로그 클리어됨
                last_count = current_count
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/logs/clear")
async def clear_logs_api():
    """로그 초기화"""
    clear_logs()
    add_log("system", "🗑️ 콘솔 로그가 초기화되었습니다")
    return {"status": "cleared"}


# =============================================================================
# Cron Logs (크론 실행 기록 + KST 변환)
# =============================================================================

from datetime import timezone, timedelta

# KST 타임존 (UTC+9)
KST = timezone(timedelta(hours=9))


def to_kst(dt):
    """UTC datetime을 KST 문자열로 변환"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kst_dt = dt.astimezone(KST)
    return kst_dt.strftime("%Y-%m-%d %H:%M:%S")


@app.get("/api/cron/logs")
async def get_cron_logs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """크론 실행 기록 조회 (KST 변환 포함)"""
    from .models.cron_log import CronLog
    
    logs = db.query(CronLog).order_by(CronLog.run_at.desc()).limit(limit).all()
    
    return {
        "logs": [
            {
                "id": log.id,
                "run_at": log.run_at.isoformat() if log.run_at else None,
                "run_at_kst": to_kst(log.run_at),  # KST 변환
                "keyword": log.keyword,
                "fetched": log.fetched,
                "inserted": log.inserted,
                "skipped": log.skipped,
                "duration_ms": log.duration_ms,
                "status": log.status,
                "error_message": log.error_message,
                "pmid_range_start": log.pmid_range_start,
                "pmid_range_end": log.pmid_range_end,
                "db_before": log.db_before,
                "db_after": log.db_after,
            }
            for log in logs
        ],
        "total": len(logs),

    }


@app.get("/api/cron/stats/today")
async def get_today_stats(db: Session = Depends(get_db)):
    """오늘 기준 통계"""
    from .models.cron_log import CronLog
    from .models.paper import Paper as PaperModel
    from datetime import date
    
    today = date.today()
    
    # 오늘 크론 실행 기록
    today_logs = db.query(CronLog).filter(
        func.date(CronLog.run_at) == today
    ).all()
    
    # 오늘 통계 계산
    runs_today = len(today_logs)
    inserted_today = sum(log.inserted for log in today_logs)
    skipped_today = sum(log.skipped for log in today_logs)
    successful_runs = sum(1 for log in today_logs if log.status == "success")
    failed_runs = sum(1 for log in today_logs if log.status == "error")
    
    # 전체 논문 수
    total_papers = db.query(func.count(PaperModel.pmid)).scalar()
    
    # 오늘 추가된 논문 (created_at 기준)
    papers_added_today = db.query(func.count(PaperModel.pmid)).filter(
        func.date(PaperModel.created_at) == today
    ).scalar()
    
    return {
        "date": today.isoformat(),
        "runs_today": runs_today,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "inserted_today": inserted_today,
        "skipped_today": skipped_today,
        "papers_added_today": papers_added_today,
        "total_papers": total_papers,
    }


@app.post("/api/cron/run")
async def run_cron_manually(
    term: str = Query("breast cancer", description="검색 키워드"),
    limit: int = Query(100, ge=1, le=1000, description="수집할 논문 수"),
):
    """크론 수동 실행"""
    try:
        job = await etl_worker.start_etl(
            term=term,
            limit=limit,
            offset=0,  # TODO: Resume 지원
        )
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "message": f"Cron started for '{term}' (limit={limit})",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Database Tables Admin
# =============================================================================

@app.get("/api/db/tables")
async def get_db_tables(db: Session = Depends(get_db)):
    """모든 테이블 목록 및 row 수 (모델 등록 + 미등록 포함)"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    from .models.cron_log import CronLog
    from sqlalchemy import inspect, text
    from datetime import datetime
    
    # 등록된 모델 정보
    registered_models = {
        "papers": {"model": PaperModel, "pk": "pmid", "description": "논문 메타데이터 및 임베딩"},
        "embedding_tasks": {"model": EmbeddingTask, "pk": "id", "description": "임베딩 작업 대기열"},
        "cron_logs": {"model": CronLog, "pk": "id", "description": "ETL 크론 실행 기록"},
    }
    
    def get_model_table_info(model, name: str, description: str, pk_field: str):
        try:
            count = db.query(func.count(getattr(model, pk_field))).scalar()
            latest = None
            if hasattr(model, 'created_at'):
                latest_row = db.query(model.created_at).order_by(model.created_at.desc()).first()
                if latest_row:
                    latest = latest_row[0].isoformat() if latest_row[0] else None
            
            return {
                "name": name,
                "count": count,
                "description": description,
                "latest_update": latest,
                "estimated_size_mb": round(count * 0.002, 2),
                "registered": True,
            }
        except Exception:
            # 테이블이 DB에 없으면 None 반환
            return None
    
    def get_raw_table_info(table_name: str, description: str = "미등록 테이블"):
        """테이블 정보 조회 (raw SQL)"""
        try:
            count_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            return {
                "name": table_name,
                "count": count_result,
                "description": description,
                "latest_update": None,
                "estimated_size_mb": round(count_result * 0.001, 2),
                "registered": False,
            }
        except Exception:
            return None
    
    # DB에 실제 존재하는 테이블 목록 먼저 조회
    inspector = inspect(db.get_bind())
    all_db_tables = set(inspector.get_table_names())
    
    # 1. 등록된 모델 테이블 (실제 DB에 존재하는 것만)
    registered_tables = []
    for name, info in registered_models.items():
        if name in all_db_tables:
            table_info = get_model_table_info(
                info["model"], name, info["description"], info["pk"]
            )
            if table_info:
                registered_tables.append(table_info)
    
    # 2. 미등록 테이블 (등록된 모델 이외의 테이블)
    registered_names = set(registered_models.keys())
    unregistered_names = all_db_tables - registered_names
    
    # 3. 미등록 테이블 정보 수집
    unregistered_tables = []
    for table_name in sorted(unregistered_names):
        if table_name.startswith("alembic") or table_name.startswith("_"):
            continue  # 마이그레이션/시스템 테이블 제외
        info = get_raw_table_info(table_name)
        if info:
            unregistered_tables.append(info)
    
    return {
        "registered_tables": registered_tables,
        "unregistered_tables": unregistered_tables,
        "total_tables": len(registered_tables) + len(unregistered_tables),
    }


@app.get("/api/db/table/{table_name}")
async def get_table_detail(
    table_name: str,
    db: Session = Depends(get_db),
):
    """테이블 상세 정보"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    from .models.cron_log import CronLog
    
    table_map = {
        "papers": {
            "model": PaperModel,
            "pk": "pmid",
            "columns": ["pmid", "title", "journal", "pubdate", "embedding_status", "created_at"],
            "filterable": ["embedding_status", "journal", "pubdate"],
        },
        "embedding_tasks": {
            "model": EmbeddingTask,
            "pk": "id",
            "columns": ["id", "pmid", "text_type", "status", "created_at"],
            "filterable": ["status", "text_type"],
        },
        "cron_logs": {
            "model": CronLog,
            "pk": "id",
            "columns": ["id", "keyword", "inserted", "skipped", "status", "run_at"],
            "filterable": ["status", "keyword"],
        },
    }
    
    if table_name not in table_map:
        raise HTTPException(status_code=404, detail=f"테이블 없음: {table_name}")
    
    info = table_map[table_name]
    model = info["model"]
    pk = info["pk"]
    
    count = db.query(func.count(getattr(model, pk))).scalar()
    
    return {
        "name": table_name,
        "count": count,
        "columns": info["columns"],
        "filterable_columns": info["filterable"],
        "primary_key": pk,
    }


@app.get("/api/db/table/{table_name}/rows")
async def get_table_rows(
    table_name: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=10000),  # 전체 보기 지원
    sort: str = Query(None),
    order: str = Query("desc"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """테이블별 실제 데이터 조회 (KST 변환 포함)"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    from .models.cron_log import CronLog
    
    table_config = {
        "papers": {
            "model": PaperModel,
            "pk": "pmid",
            "sort_default": "created_at",
            "search_fields": ["title", "pmid", "journal"],
            "columns": ["pmid", "title", "journal", "pubdate", "embedding_status", "created_at"],
        },
        "embedding_tasks": {
            "model": EmbeddingTask,
            "pk": "id",
            "sort_default": "created_at",
            "search_fields": ["pmid"],
            "columns": ["id", "pmid", "text_type", "status", "created_at"],
        },
        "cron_logs": {
            "model": CronLog,
            "pk": "id",
            "sort_default": "run_at",
            "search_fields": ["keyword"],
            "columns": ["id", "keyword", "inserted", "skipped", "offset_start", "offset_end", "status", "duration_ms", "run_at"],
        },
    }
    
    from sqlalchemy import inspect, text
    inspector = inspect(db.get_bind())
    all_db_tables = set(inspector.get_table_names())
    
    # 미등록 테이블이거나, 등록 테이블이지만 DB에 존재하지 않으면 raw SQL 사용
    if table_name not in table_config or table_name not in all_db_tables:
        
        try:
            if table_name not in all_db_tables:
                raise HTTPException(status_code=404, detail=f"테이블 없음: {table_name}")
            
            # 컬럼 정보 가져오기
            columns_info = inspector.get_columns(table_name)
            columns = [col['name'] for col in columns_info]
            
            # 총 개수
            total_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            
            # 데이터 조회 (페이지네이션)
            offset = (page - 1) * per_page
            rows_result = db.execute(text(
                f"SELECT * FROM {table_name} LIMIT {per_page} OFFSET {offset}"
            ))
            
            rows_data = []
            for row in rows_result:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, 'isoformat'):
                        row_dict[col] = val.isoformat()
                    else:
                        row_dict[col] = str(val) if val is not None else None
                rows_data.append(row_dict)
            
            return {
                "table": table_name,
                "rows": rows_data,
                "total": total_result,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_result + per_page - 1) // per_page,
                "columns": columns,
                "registered": False,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"테이블 조회 오류: {str(e)}")
    
    config = table_config[table_name]
    model = config["model"]
    pk = config["pk"]
    sort_field = sort or config["sort_default"]
    
    query = db.query(model)
    
    # 검색
    if search:
        search_term = f"%{search}%"
        conditions = []
        for field in config["search_fields"]:
            if hasattr(model, field):
                conditions.append(getattr(model, field).ilike(search_term))
        if conditions:
            from sqlalchemy import or_
            query = query.filter(or_(*conditions))
    
    # 총 개수
    total = query.count()
    
    # 정렬
    if hasattr(model, sort_field):
        sort_col = getattr(model, sort_field)
        if order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())
    
    # 페이지네이션
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # 결과 변환 (KST 적용)
    def row_to_dict(row):
        result = {}
        for col in config["columns"]:
            val = getattr(row, col, None)
            if col in ["created_at", "run_at"] and val:
                result[col] = val.isoformat() if val else None
                result[f"{col}_kst"] = to_kst(val)
            elif isinstance(val, list):
                result[col] = val
            else:
                result[col] = str(val) if val is not None else None
        return result
    
    return {
        "table": table_name,
        "rows": [row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
        "columns": config["columns"],
    }


class PartialDeleteRequest(BaseModel):
    condition_type: str  # date_before, date_after, status, keyword
    condition_value: str
    confirm: str


@app.post("/api/db/table/{table_name}/preview-delete")
async def preview_delete(
    table_name: str,
    condition_type: str = Query(...),
    condition_value: str = Query(...),
    db: Session = Depends(get_db),
):
    """조건부 삭제 미리보기 (영향받는 row 수)"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    from .models.cron_log import CronLog
    from datetime import datetime
    
    table_map = {
        "papers": PaperModel,
        "embedding_tasks": EmbeddingTask,
        "cron_logs": CronLog,
    }
    
    if table_name not in table_map:
        raise HTTPException(status_code=404, detail=f"테이블 없음: {table_name}")
    
    model = table_map[table_name]
    query = db.query(model)
    
    # 조건 적용
    try:
        if condition_type == "date_before":
            date = datetime.fromisoformat(condition_value)
            if hasattr(model, 'created_at'):
                query = query.filter(model.created_at < date)
            elif hasattr(model, 'run_at'):
                query = query.filter(model.run_at < date)
        elif condition_type == "date_after":
            date = datetime.fromisoformat(condition_value)
            if hasattr(model, 'created_at'):
                query = query.filter(model.created_at > date)
            elif hasattr(model, 'run_at'):
                query = query.filter(model.run_at > date)
        elif condition_type == "status":
            if hasattr(model, 'status'):
                query = query.filter(model.status == condition_value)
            elif hasattr(model, 'embedding_status'):
                query = query.filter(model.embedding_status == condition_value)
        elif condition_type == "keyword":
            if hasattr(model, 'title'):
                query = query.filter(model.title.ilike(f"%{condition_value}%"))
            elif hasattr(model, 'keyword'):
                query = query.filter(model.keyword.ilike(f"%{condition_value}%"))
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 조건: {condition_type}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"조건 파싱 오류: {str(e)}")
    
    affected = query.count()
    
    return {
        "table": table_name,
        "condition_type": condition_type,
        "condition_value": condition_value,
        "affected_rows": affected,
    }


@app.delete("/api/db/table/{table_name}/partial")
async def partial_delete(
    table_name: str,
    request: PartialDeleteRequest,
    db: Session = Depends(get_db),
):
    """조건부 삭제 실행"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    from .models.cron_log import CronLog
    from datetime import datetime
    import time
    
    if request.confirm != "DELETE":
        raise HTTPException(status_code=400, detail="확인 필요: 'DELETE' 입력")
    
    table_map = {
        "papers": PaperModel,
        "embedding_tasks": EmbeddingTask,
        "cron_logs": CronLog,
    }
    
    if table_name not in table_map:
        raise HTTPException(status_code=404, detail=f"테이블 없음: {table_name}")
    
    model = table_map[table_name]
    query = db.query(model)
    
    start_time = time.time()
    
    # 조건 적용
    try:
        if request.condition_type == "date_before":
            date = datetime.fromisoformat(request.condition_value)
            if hasattr(model, 'created_at'):
                query = query.filter(model.created_at < date)
            elif hasattr(model, 'run_at'):
                query = query.filter(model.run_at < date)
        elif request.condition_type == "date_after":
            date = datetime.fromisoformat(request.condition_value)
            if hasattr(model, 'created_at'):
                query = query.filter(model.created_at > date)
            elif hasattr(model, 'run_at'):
                query = query.filter(model.run_at > date)
        elif request.condition_type == "status":
            if hasattr(model, 'status'):
                query = query.filter(model.status == request.condition_value)
            elif hasattr(model, 'embedding_status'):
                query = query.filter(model.embedding_status == request.condition_value)
        elif request.condition_type == "keyword":
            if hasattr(model, 'title'):
                query = query.filter(model.title.ilike(f"%{request.condition_value}%"))
            elif hasattr(model, 'keyword'):
                query = query.filter(model.keyword.ilike(f"%{request.condition_value}%"))
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 조건: {request.condition_type}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"조건 파싱 오류: {str(e)}")
    
    deleted = query.delete(synchronize_session=False)
    db.commit()
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    add_log("warning", f"조건부 삭제: {table_name} | {request.condition_type}={request.condition_value} | {deleted} rows | {duration_ms}ms")
    
    return {
        "table": table_name,
        "deleted": deleted,
        "condition_type": request.condition_type,
        "condition_value": request.condition_value,
        "duration_ms": duration_ms,
    }


@app.delete("/api/db/table/{table_name}/full")
async def full_delete_table(
    table_name: str,
    confirm: str = Query(..., description="'DELETE' 입력 필요"),
    db: Session = Depends(get_db),
):
    """테이블 전체 삭제"""
    from .models.paper import Paper as PaperModel, EmbeddingTask
    from .models.cron_log import CronLog
    import time
    
    if confirm != "DELETE":
        raise HTTPException(status_code=400, detail="확인 필요: 'DELETE' 입력")
    
    table_map = {
        "papers": PaperModel,
        "embedding_tasks": EmbeddingTask,
        "cron_logs": CronLog,
    }
    
    if table_name not in table_map:
        raise HTTPException(status_code=404, detail=f"테이블 없음: {table_name}")
    
    model = table_map[table_name]
    
    start_time = time.time()
    count = db.query(model).count()
    db.query(model).delete()
    db.commit()
    duration_ms = int((time.time() - start_time) * 1000)
    
    add_log("warning", f"전체 삭제: {table_name} | {count} rows | {duration_ms}ms")
    
    return {
        "table": table_name,
        "deleted": count,
        "duration_ms": duration_ms,
    }
