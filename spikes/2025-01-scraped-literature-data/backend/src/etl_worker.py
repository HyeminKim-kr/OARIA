"""
OARIA Spike - ETL Worker

PubMed 논문을 수집하여 SQL에 저장하는 ETL 파이프라인입니다.

처리 흐름:
1. PubMed 검색 → PMID 리스트
2. ESummary → 메타데이터 수집
3. EFetch → Abstract 수집
4. SQL 저장
5. 임베딩 작업 등록

이 설계의 이유:
- 배치 처리로 대량 데이터 효율적 수집
- 중간 저장으로 데이터 손실 방지
- 비동기 처리로 높은 처리량
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .db import get_db_session
from .models.paper import Paper, EmbeddingTask
from .pubmed_client import PubMedClient


@dataclass
class ETLJob:
    """ETL 작업 상태"""
    job_id: str
    term: str
    offset: int = 0
    limit: int = 100
    batch_size: int = 500
    collected: int = 0
    total: int = 0
    status: str = "idle"  # idle, running, completed, error
    message: str = ""
    started_at: Optional[datetime] = None
    _stop_requested: bool = False


class ETLWorker:
    """
    ETL Worker
    
    PubMed 논문을 수집하여 데이터베이스에 저장합니다.
    """
    
    def __init__(self):
        self.jobs: dict[str, ETLJob] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
    
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
        """백그라운드 ETL 실행"""
        try:
            async with PubMedClient() as client:
                # 총 건수 확인
                job.total = await client.get_count(job.term, date_from, date_to)
                job.message = f"Found {job.total} papers"
                
                current_offset = job.offset
                remaining = min(job.limit, job.total - job.offset)
                
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
                    
                    # SQL 저장
                    saved_count = await self._save_papers(papers)
                    
                    job.collected += saved_count
                    current_offset += len(papers)
                    remaining -= len(papers)
                    
                    # 진행률 로그
                    progress = (job.collected / job.limit) * 100 if job.limit > 0 else 0
                    job.message = f"Collected {job.collected}/{job.limit} ({progress:.1f}%)"
                    print(f"[ETL {job.job_id}] {job.message}")
                    
                    # 배치 사이 약간의 딜레이
                    await asyncio.sleep(0.1)
                
                job.status = "completed" if not job._stop_requested else "stopped"
                job.message = f"ETL completed. {job.collected} papers saved."
                
        except Exception as e:
            job.status = "error"
            job.message = str(e)
            print(f"[ETL {job.job_id}] Error: {e}")
    
    async def _save_papers(self, papers: list[dict]) -> int:
        """논문 데이터를 SQL에 저장"""
        saved_count = 0
        
        with get_db_session() as db:
            for paper_data in papers:
                pmid = paper_data.get("pmid")
                
                # 이미 존재하는지 확인
                existing = db.query(Paper).filter(Paper.pmid == pmid).first()
                
                if existing:
                    # 업데이트
                    existing.title = paper_data.get("title", existing.title)
                    existing.abstract = paper_data.get("abstract", existing.abstract)
                    existing.authors = paper_data.get("authors", existing.authors)
                    existing.journal = paper_data.get("journal", existing.journal)
                    existing.pubdate = paper_data.get("pubdate", existing.pubdate)
                    existing.doi = paper_data.get("doi", existing.doi)
                else:
                    # 새로 생성
                    paper = Paper(
                        pmid=pmid,
                        title=paper_data.get("title", ""),
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
                
                saved_count += 1
            
            db.commit()
        
        return saved_count
    
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
            "total": job.total,
            "message": job.message,
        }
    
    async def stop_etl(self, job_id: str) -> bool:
        """ETL 중단"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        job._stop_requested = True
        job.status = "stopped"
        
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
