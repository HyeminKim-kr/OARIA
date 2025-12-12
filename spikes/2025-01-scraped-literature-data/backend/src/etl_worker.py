"""
OARIA Literature - ETL Worker (Enhanced)

PubMed 논문을 수집하여 SQL에 저장하는 ETL 파이프라인입니다.

주요 기능:
1. 상세 로깅: Before/After/Inserted/Skipped + PMID 범위
2. 중복 감지: PMID 기반 중복 스킵
3. CronLog 기록: 각 실행의 통계 저장
4. 실시간 콘솔 로그 스트리밍
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .db import get_db_session
from .models.paper import Paper, EmbeddingTask
from .models.cron_log import CronLog
from .pubmed_client import PubMedClient


# 실시간 로그 저장소 (SSE 스트리밍용)
_log_store: List[dict] = []
_log_max_size = 1000


def add_log(level: str, message: str, job_id: str = None):
    """로그 추가 (콘솔 출력 + 저장)"""
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "job_id": job_id,
    }
    _log_store.append(log_entry)
    if len(_log_store) > _log_max_size:
        _log_store.pop(0)
    
    # 콘솔에도 출력
    icon = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}.get(level, "📝")
    print(f"[{timestamp[11:19]}] {icon} {message}")


def get_logs(limit: int = 100) -> List[dict]:
    """로그 조회"""
    return _log_store[-limit:]


def clear_logs():
    """로그 클리어"""
    _log_store.clear()


@dataclass
class ETLJob:
    """ETL 작업 상태"""
    job_id: str
    term: str
    offset: int = 0
    limit: int = 100
    batch_size: int = 500
    collected: int = 0
    inserted: int = 0
    skipped: int = 0
    total: int = 0
    db_before: int = 0
    db_after: int = 0
    pmid_range_start: str = ""
    pmid_range_end: str = ""
    status: str = "idle"  # idle, running, completed, error, stopped
    message: str = ""
    started_at: Optional[datetime] = None
    duration_ms: int = 0
    _stop_requested: bool = False


class ETLWorker:
    """
    ETL Worker (Enhanced)
    
    상세 로깅 + 중복 감지 + CronLog 저장
    """
    
    def __init__(self):
        self.jobs: dict[str, ETLJob] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
    
    async def add_log(self, level: str, message: str, job_id: str = None):
        """로그 추가 (비동기 호환)"""
        add_log(level, message, job_id)
    
    async def start_etl(
        self,
        term: str,
        offset: int = 0,
        limit: int = 100,
        batch_size: int = 500,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> ETLJob:
        """ETL 시작"""
        job_id = str(uuid.uuid4())[:8]
        
        job = ETLJob(
            job_id=job_id,
            term=term,
            offset=offset,
            limit=limit,
            batch_size=batch_size,
            status="running",
            started_at=datetime.now(),
        )
        
        self.jobs[job_id] = job
        
        # 초기 로그
        add_log("info", f'Search Term = "{term}"', job_id)
        
        # 백그라운드 태스크 시작
        task = asyncio.create_task(
            self._run_etl(job, date_from, date_to)
        )
        self._running_tasks[job_id] = task
        
        return job
    
    async def _run_etl(
        self, 
        job: ETLJob,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        """백그라운드 ETL 실행 (상세 로깅)"""
        start_time = time.time()
        
        try:
            # DB Before 상태 조회
            with get_db_session() as db:
                job.db_before = db.query(Paper).count()
            
            add_log("info", f"📊 DB Before: {job.db_before:,} papers", job.job_id)
            
            async with PubMedClient() as client:
                # 총 건수 확인
                job.total = await client.get_count(job.term, date_from, date_to)
                add_log("info", f"🔍 PubMed Total: {job.total:,} results", job.job_id)
                
                current_offset = job.offset
                remaining = min(job.limit, job.total - job.offset)
                
                inserted_pmids: List[str] = []
                
                while remaining > 0 and not job._stop_requested:
                    batch_limit = min(job.batch_size, remaining)
                    
                    # 배치 수집
                    papers, _ = await client.search_and_fetch(
                        term=job.term,
                        offset=current_offset,
                        limit=batch_limit,
                        date_from=date_from,
                        date_to=date_to,
                    )
                    
                    add_log("info", f"🔄 Fetched {len(papers)} papers (offset: {current_offset})", job.job_id)
                    
                    # SQL 저장 (중복 감지)
                    batch_inserted, batch_skipped, new_pmids = await self._save_papers_with_stats(papers)
                    
                    job.inserted += batch_inserted
                    job.skipped += batch_skipped
                    job.collected += batch_inserted
                    inserted_pmids.extend(new_pmids)
                    
                    if batch_inserted > 0 or batch_skipped > 0:
                        add_log("success", f"💾 Inserted: {batch_inserted} | Skipped (dup): {batch_skipped}", job.job_id)
                    
                    current_offset += len(papers)
                    remaining -= len(papers)
                    
                    if len(papers) == 0:
                        break
                    
                    # 배치 사이 딜레이
                    await asyncio.sleep(0.2)
                
                # PMID 범위
                if inserted_pmids:
                    job.pmid_range_start = inserted_pmids[0]
                    job.pmid_range_end = inserted_pmids[-1]
                    add_log("info", f"📍 PMID Range: {job.pmid_range_start} → {job.pmid_range_end}", job.job_id)
                
                # DB After 상태 조회
                with get_db_session() as db:
                    job.db_after = db.query(Paper).count()
                
                add_log("info", f"📊 DB After: {job.db_after:,} papers (+{job.db_after - job.db_before})", job.job_id)
                
                job.status = "completed" if not job._stop_requested else "stopped"
                job.message = f"Inserted: {job.inserted} | Skipped: {job.skipped}"
                job.duration_ms = int((time.time() - start_time) * 1000)
                
                add_log("success", f"✅ ETL 완료! Inserted: {job.inserted}, Skipped: {job.skipped}, Duration: {job.duration_ms}ms", job.job_id)
                
                # CronLog 저장
                await self._save_cron_log(job)
                
        except Exception as e:
            job.status = "error"
            job.message = str(e)
            job.duration_ms = int((time.time() - start_time) * 1000)
            add_log("error", f"❌ Error: {e}", job.job_id)
            
            # 에러도 CronLog에 기록
            await self._save_cron_log(job, error_message=str(e))
    
    async def _save_papers_with_stats(self, papers: list[dict]) -> tuple[int, int, List[str]]:
        """논문 저장 + 통계 (inserted, skipped, new_pmids)"""
        inserted_count = 0
        skipped_count = 0
        new_pmids = []
        
        with get_db_session() as db:
            for paper_data in papers:
                pmid = paper_data.get("pmid")
                if not pmid:
                    continue
                
                # 중복 체크
                existing = db.query(Paper).filter(Paper.pmid == pmid).first()
                
                if existing:
                    # 이미 존재하면 스킵
                    skipped_count += 1
                else:
                    # 새로 생성
                    title = paper_data.get("title", "")
                    paper = Paper(
                        pmid=pmid,
                        title=title,
                        abstract=paper_data.get("abstract", ""),
                        authors=paper_data.get("authors", []),
                        journal=paper_data.get("journal"),
                        pubdate=paper_data.get("pubdate"),
                        doi=paper_data.get("doi"),
                    )
                    db.add(paper)
                    
                    # 임베딩 작업 등록
                    embedding_task = EmbeddingTask(
                        pmid=pmid,
                        text_type="abstract",
                    )
                    db.add(embedding_task)
                    
                    inserted_count += 1
                    new_pmids.append(pmid)
                    
                    # 제목 truncate해서 로그 출력 (매 10개마다)
                    if inserted_count <= 3 or inserted_count % 10 == 0:
                        title_short = (title[:60] + "...") if len(title) > 60 else title
                        add_log("db", f"📄 [{pmid}] {title_short}")
            
            db.commit()
        
        return inserted_count, skipped_count, new_pmids
    
    async def _save_cron_log(self, job: ETLJob, error_message: str = None):
        """CronLog 저장"""
        try:
            with get_db_session() as db:
                cron_log = CronLog(
                    keyword=job.term,
                    fetched=job.inserted + job.skipped,
                    inserted=job.inserted,
                    skipped=job.skipped,
                    duration_ms=job.duration_ms,
                    status="error" if error_message else "success",
                    error_message=error_message,
                    pmid_range_start=job.pmid_range_start,
                    pmid_range_end=job.pmid_range_end,
                    offset_start=job.offset,  # 배치 시작 위치
                    offset_end=job.offset + job.collected,  # 배치 끝 위치 (다음 시작점)
                    db_before=job.db_before,
                    db_after=job.db_after,
                )
                db.add(cron_log)
                db.commit()
                add_log("info", "📝 CronLog saved", job.job_id)
        except Exception as e:
            add_log("warning", f"CronLog 저장 실패: {e}", job.job_id)
    
    def get_status(self, job_id: str) -> Optional[dict]:
        """ETL 상태 조회"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        progress = 0.0
        if job.limit > 0:
            progress = min((job.collected / job.limit) * 100, 100.0)
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "progress": progress,
            "collected": job.collected,
            "inserted": job.inserted,
            "skipped": job.skipped,
            "total": job.total,
            "db_before": job.db_before,
            "db_after": job.db_after,
            "pmid_range_start": job.pmid_range_start,
            "pmid_range_end": job.pmid_range_end,
            "message": job.message,
            "duration_ms": job.duration_ms,
        }
    
    async def stop_etl(self, job_id: str) -> bool:
        """ETL 중단"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        job._stop_requested = True
        job.status = "stopped"
        add_log("warning", "⏹️ ETL 중단됨", job_id)
        
        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        return True


# 싱글톤 인스턴스
etl_worker = ETLWorker()
