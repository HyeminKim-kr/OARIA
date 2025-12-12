"""
OARIA Literature - Embedding Worker

PubMedBERT 기반 임베딩을 생성하고 Qdrant에 저장하는 워커입니다.

처리 흐름:
1. embedding_tasks 테이블에서 pending 작업 조회
2. 논문 텍스트 로드
3. PubMedBERT로 임베딩 생성
4. Qdrant에 저장
5. 상태 업데이트

설계 이유:
- 비동기 백그라운드 처리로 API 응답 지연 방지
- 배치 처리로 GPU 활용 최적화
- 실패한 작업 재시도 가능
"""

import asyncio
from datetime import datetime
from typing import Optional
from sentence_transformers import SentenceTransformer

from sqlalchemy.orm import Session
from sqlalchemy import func

from .config import settings
from .db import get_db_session, SessionLocal
from .models.paper import Paper, EmbeddingTask, EmbeddingStatus
from .qdrant_client import get_qdrant_client


class EmbeddingWorker:
    """
    Embedding Worker
    
    백그라운드에서 임베딩 작업을 처리합니다.
    """
    
    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def _get_model(self) -> SentenceTransformer:
        """임베딩 모델 로드 (지연 로딩)"""
        if self._model is None:
            print(f"🧠 Loading embedding model: {settings.embedding_model}")
            self._model = SentenceTransformer(settings.embedding_model)
            print(f"✅ Model loaded (dimension: {self._model.get_sentence_embedding_dimension()})")
        return self._model
    
    def encode(self, text: str) -> list[float]:
        """텍스트를 임베딩으로 변환"""
        model = self._get_model()
        embedding = model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    
    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩"""
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_tensor=False, batch_size=32)
        return [e.tolist() for e in embeddings]
    
    async def process_pending_tasks(self, batch_size: int = 10) -> int:
        """pending 상태의 임베딩 작업 처리"""
        processed = 0
        
        with get_db_session() as db:
            # pending 작업 조회
            tasks = (
                db.query(EmbeddingTask)
                .filter(EmbeddingTask.status == EmbeddingStatus.PENDING.value)
                .limit(batch_size)
                .all()
            )
            
            if not tasks:
                return 0
            
            # PMID 목록
            pmids = [t.pmid for t in tasks]
            
            # 논문 데이터 로드
            papers = (
                db.query(Paper)
                .filter(Paper.pmid.in_(pmids))
                .all()
            )
            paper_map = {p.pmid: p for p in papers}
            
            # 텍스트 준비
            texts = []
            valid_tasks = []
            for task in tasks:
                paper = paper_map.get(task.pmid)
                if paper and paper.abstract:
                    texts.append(f"{paper.title} {paper.abstract}")
                    valid_tasks.append(task)
                    task.status = EmbeddingStatus.PROCESSING.value
                else:
                    task.status = EmbeddingStatus.ERROR.value
                    task.error_message = "Paper or abstract not found"
            
            db.commit()
            
            if not texts:
                return 0
            
            # 임베딩 생성 (CPU/GPU 연산)
            try:
                embeddings = await asyncio.to_thread(self.encode_batch, texts)
            except Exception as e:
                # 실패 처리
                for task in valid_tasks:
                    task.status = EmbeddingStatus.ERROR.value
                    task.error_message = str(e)
                db.commit()
                raise
            
            # Qdrant에 저장
            qdrant = get_qdrant_client()
            items = []
            for task, embedding in zip(valid_tasks, embeddings):
                paper = paper_map[task.pmid]
                items.append({
                    "pmid": task.pmid,
                    "embedding": embedding,
                    "payload": {
                        "title": paper.title,
                        "abstract": paper.abstract[:500],  # 페이로드 크기 제한
                        "authors": paper.authors[:5] if paper.authors else [],
                        "journal": paper.journal,
                        "pubdate": paper.pubdate,
                    },
                })
            
            qdrant.upsert_batch(items)
            
            # 상태 업데이트
            for task in valid_tasks:
                task.status = EmbeddingStatus.DONE.value
                task.processed_at = datetime.utcnow()
                
                # 논문 상태도 업데이트
                paper = paper_map.get(task.pmid)
                if paper:
                    paper.embedding_status = EmbeddingStatus.DONE.value
            
            db.commit()
            processed = len(valid_tasks)
        
        return processed
    
    async def run_worker(self, interval: float = 5.0):
        """백그라운드 워커 실행"""
        self._running = True
        print("🚀 Embedding worker started")
        
        while self._running:
            try:
                processed = await self.process_pending_tasks()
                if processed > 0:
                    print(f"✅ Processed {processed} embedding tasks")
            except Exception as e:
                print(f"❌ Embedding worker error: {e}")
            
            await asyncio.sleep(interval)
        
        print("👋 Embedding worker stopped")
    
    async def start(self):
        """워커 시작 (백그라운드)"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_worker())
    
    async def stop(self):
        """워커 중단"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    def get_status(self) -> dict:
        """임베딩 상태 통계"""
        db = SessionLocal()
        try:
            stats = (
                db.query(
                    EmbeddingTask.status,
                    func.count(EmbeddingTask.id).label("count")
                )
                .group_by(EmbeddingTask.status)
                .all()
            )
            
            result = {
                "pending": 0,
                "processing": 0,
                "done": 0,
                "error": 0,
            }
            total = 0
            for status, count in stats:
                result[status] = count
                total += count
            
            result["total"] = total
            return result
        finally:
            db.close()


# 싱글톤 인스턴스
embedding_worker = EmbeddingWorker()
