"""
배치 크롤러 - 대량 논문 수집 관리

100만 건 이상의 논문을 안정적으로 수집하기 위한 배치 처리 시스템입니다.

주요 기능:
1. 배치 단위 처리 (기본 500건/배치)
2. 진행 상태 추적 및 저장
3. 중단/재개 기능
4. 메모리 효율적 처리 (스트리밍 방식)

설계 의도:
- 100만건 / 500건(배치) = 2,000 배치
- 3 req/sec → 1배치당 약 1초 (search + summary + fetch)
- 안전 마진 포함 → 100만건 약 40-70시간
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from models import Paper, CrawlStatusResponse
from pubmed_client import PubMedClient


@dataclass
class CrawlJob:
    """크롤링 작업 상태"""
    job_id: str
    term: str
    offset: int = 0
    limit: int = 1000
    batch_size: int = 500
    collected: int = 0
    total: int = 0
    status: str = "idle"  # idle, running, paused, completed, error
    started_at: Optional[datetime] = None
    papers: list[Paper] = field(default_factory=list)
    error_message: str = ""
    _stop_requested: bool = False


class BatchCrawler:
    """
    배치 크롤러
    
    대량의 논문을 배치 단위로 수집합니다.
    UI에서 진행률을 확인하고 중단/재개할 수 있습니다.
    
    사용 예시:
    ```python
    crawler = BatchCrawler()
    job = await crawler.start_crawl("breast cancer", limit=1000)
    
    # 상태 확인
    status = crawler.get_status(job.job_id)
    
    # 중단
    await crawler.stop_crawl(job.job_id)
    ```
    """
    
    def __init__(self):
        self.jobs: dict[str, CrawlJob] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
    
    async def start_crawl(
        self,
        term: str,
        offset: int = 0,
        limit: int = 1000,
        batch_size: int = 500,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> CrawlJob:
        """
        크롤링 시작
        
        Args:
            term: 검색 키워드
            offset: 시작 위치
            limit: 수집할 총 논문 수
            batch_size: 배치당 논문 수 (기본 500)
            
        Returns:
            CrawlJob 객체
        """
        job_id = str(uuid.uuid4())[:8]
        
        job = CrawlJob(
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
            self._run_crawl(job, date_from, date_to)
        )
        self._running_tasks[job_id] = task
        
        return job
    
    async def _run_crawl(
        self, 
        job: CrawlJob,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        """백그라운드 크롤링 실행"""
        try:
            async with PubMedClient() as client:
                # 총 건수 확인
                job.total = await client.get_count(job.term, date_from, date_to)
                
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
                    
                    job.papers.extend(papers)
                    job.collected += len(papers)
                    current_offset += len(papers)
                    remaining -= len(papers)
                    
                    # 진행률 로그
                    progress = (job.collected / job.limit) * 100
                    print(f"[Crawl {job.job_id}] {job.collected}/{job.limit} ({progress:.1f}%)")
                    
                    # 배치 사이 약간의 딜레이 (안정성)
                    await asyncio.sleep(0.1)
                
                job.status = "completed" if not job._stop_requested else "paused"
                
        except Exception as e:
            job.status = "error"
            job.error_message = str(e)
            print(f"[Crawl {job.job_id}] Error: {e}")
    
    def get_status(self, job_id: str) -> Optional[CrawlStatusResponse]:
        """크롤링 상태 조회"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        progress = 0.0
        if job.limit > 0:
            progress = min((job.collected / job.limit) * 100, 100.0)
        
        return CrawlStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress=progress,
            collected=job.collected,
            total=job.total,
            current_offset=job.offset + job.collected,
            started_at=job.started_at,
            papers=job.papers[-20:] if job.papers else [],  # 최근 20건만
        )
    
    async def stop_crawl(self, job_id: str) -> bool:
        """크롤링 중단"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        job._stop_requested = True
        job.status = "paused"
        
        # 태스크 취소
        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        return True
    
    def get_all_papers(self, job_id: str) -> list[Paper]:
        """수집된 모든 논문 반환"""
        job = self.jobs.get(job_id)
        if not job:
            return []
        return job.papers


# 싱글톤 인스턴스
crawler = BatchCrawler()
