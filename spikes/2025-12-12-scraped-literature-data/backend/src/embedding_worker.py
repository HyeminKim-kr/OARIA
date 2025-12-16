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
from .etl_worker import add_log


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
            # Docker 환경(특히 Mac)에서 meta tensor 오류 방지를 위해 cpu 강제 사용
            self._model = SentenceTransformer(settings.embedding_model, device="cpu")
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
        embeddings = model.encode(texts, convert_to_tensor=False, batch_size=settings.embedding_batch_size)
        return [e.tolist() for e in embeddings]
    
    async def process_pending_tasks(self, batch_size: int = 10) -> int:
        """pending 상태의 임베딩 작업 처리"""
        processed = 0
        import time
        t_start = time.time()
        
        with get_db_session() as db:
            # pending 작업 조회
            t0 = time.time()
            tasks = (
                db.query(EmbeddingTask)
                .filter(EmbeddingTask.status == EmbeddingStatus.PENDING.value)
                .limit(batch_size)
                .all()
            )
            add_log("info", f"⏱️ [Perf] Fetch tasks: {time.time() - t0:.3f}s")
            
            if not tasks:
                # 작업이 없으면 Papers 테이블에서 누락된 작업 확인 (GCP/DB 마이그레이션 대응)
                try:
                    t1 = time.time()
                    missing_papers = (
                        db.query(Paper.pmid)
                        .outerjoin(EmbeddingTask, Paper.pmid == EmbeddingTask.pmid)
                        .filter(
                            EmbeddingTask.id == None,
                            Paper.embedding_status != EmbeddingStatus.DONE.value
                        )
                        .limit(batch_size)
                        .all()
                    )
                    add_log("info", f"⏱️ [Perf] Find missing papers: {time.time() - t1:.3f}s")
                    
                    if missing_papers:
                        add_log("info", f"🔄 Creating {len(missing_papers)} missing embedding tasks...")
                        t2 = time.time()
                        new_tasks = [
                            EmbeddingTask(
                                pmid=p.pmid,
                                status=EmbeddingStatus.PENDING.value
                            )
                            for p in missing_papers
                        ]
                        db.add_all(new_tasks)
                        db.commit()
                        add_log("info", f"⏱️ [Perf] Create tasks: {time.time() - t2:.3f}s")
                        
                        # 다시 조회
                        tasks = (
                            db.query(EmbeddingTask)
                            .filter(EmbeddingTask.status == EmbeddingStatus.PENDING.value)
                            .limit(batch_size)
                            .all()
                        )
                except Exception as e:
                    add_log("error", f"⚠️ Failed to sync missing tasks: {e}")
                
                if not tasks:
                    return 0
            
            # PMID 목록
            pmids = [t.pmid for t in tasks]
            
            # 논문 데이터 로드
            t3 = time.time()
            papers = (
                db.query(Paper)
                .filter(Paper.pmid.in_(pmids))
                .all()
            )
            paper_map = {p.pmid: p for p in papers}
            add_log("info", f"⏱️ [Perf] Fetch paper details: {time.time() - t3:.3f}s")
            
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
            
            t4 = time.time()
            db.commit()
            add_log("info", f"⏱️ [Perf] Update to PROCESSING: {time.time() - t4:.3f}s")
            
            if not texts:
                return 0
            
            # 임베딩 생성 (CPU/GPU 연산)
            try:
                t5 = time.time()
                embeddings = await asyncio.to_thread(self.encode_batch, texts)
                add_log("info", f"⏱️ [Perf] Generate embeddings (n={len(texts)}): {time.time() - t5:.3f}s")
            except Exception as e:
                # 실패 처리
                for task in valid_tasks:
                    task.status = EmbeddingStatus.ERROR.value
                    task.error_message = str(e)
                db.commit()
                raise
            
            # Qdrant에 저장
            t6 = time.time()
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
            add_log("info", f"⏱️ [Perf] Qdrant upsert: {time.time() - t6:.3f}s")
            
            # 상태 업데이트
            t7 = time.time()
            for task in valid_tasks:
                task.status = EmbeddingStatus.DONE.value
                task.processed_at = datetime.utcnow()
                
                # 논문 상태도 업데이트
                paper = paper_map.get(task.pmid)
                if paper:
                    paper.embedding_status = EmbeddingStatus.DONE.value
            
            db.commit()
            add_log("info", f"⏱️ [Perf] Final DB update: {time.time() - t7:.3f}s")
            
            processed = len(valid_tasks)
        
        add_log("success", f"✅ [Perf] Total duration: {time.time() - t_start:.3f}s")
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
        """임베딩 상태 통계 (EmbeddingTask 또는 Paper 테이블에서 조회)"""
        # get_db_session()을 사용하여 현재 활성화된 DB 모드의 세션을 가져옵니다.
        with get_db_session() as db:
            # 1. EmbeddingTask 테이블에서 시도
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
                
                # EmbeddingTask에 데이터가 있으면 반환
                if total > 0:
                    result["total"] = total
                    return result
            except Exception:
                pass  # 테이블 없으면 fallback
            
            # 2. Fallback: Paper 테이블의 embedding_status에서 조회
            try:
                stats = (
                    db.query(
                        Paper.embedding_status,
                        func.count(Paper.pmid).label("count")
                    )
                    .group_by(Paper.embedding_status)
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
                    status_key = status or "pending"
                    if status_key in result:
                        result[status_key] = count
                    else:
                        result["pending"] += count  # 알 수 없는 상태는 pending으로
                    total += count
                
                result["total"] = total
                return result
            except Exception:
                # 테이블도 없고 fallback도 실패하면 빈 결과 반환
                return {
                    "pending": 0,
                    "processing": 0,
                    "done": 0,
                    "error": 0,
                    "total": 0
                }
    
    def get_sync_status(self) -> dict:
        """DB와 Qdrant 간 동기화 상태 확인"""
        qdrant = get_qdrant_client()
        
        with get_db_session() as db:
            # DB에서 DONE 상태인 PMID 목록
            done_in_db = db.query(Paper.pmid).filter(
                Paper.embedding_status == EmbeddingStatus.DONE.value
            ).all()
            done_pmids_db = set(p.pmid for p in done_in_db)
            
            # Qdrant에 있는 PMID 목록
            pmids_in_qdrant = set(qdrant.get_all_pmids())
            
            # 불일치 분석
            in_db_not_qdrant = done_pmids_db - pmids_in_qdrant  # DB에는 DONE인데 Qdrant에 없음
            in_qdrant_not_db = pmids_in_qdrant - done_pmids_db  # Qdrant에는 있는데 DB에 없음
            
            return {
                "db_done_count": len(done_pmids_db),
                "qdrant_count": len(pmids_in_qdrant),
                "missing_in_qdrant": len(in_db_not_qdrant),
                "orphan_in_qdrant": len(in_qdrant_not_db),
                "in_sync": len(in_db_not_qdrant) == 0,
                "missing_pmids": list(in_db_not_qdrant)[:100],  # 최대 100개만 반환
            }
    
    def sync_with_qdrant(self) -> dict:
        """DB의 DONE 상태 중 Qdrant에 없는 것들을 PENDING으로 리셋"""
        qdrant = get_qdrant_client()
        
        with get_db_session() as db:
            # DB에서 DONE 상태인 PMID 목록
            done_in_db = db.query(Paper.pmid).filter(
                Paper.embedding_status == EmbeddingStatus.DONE.value
            ).all()
            done_pmids_db = set(p.pmid for p in done_in_db)
            
            # Qdrant에 있는 PMID 목록
            pmids_in_qdrant = set(qdrant.get_all_pmids())
            
            # Qdrant에 없는데 DB에서 DONE인 것들 찾기
            missing_pmids = done_pmids_db - pmids_in_qdrant
            
            if missing_pmids:
                # 이들을 PENDING으로 변경
                db.query(Paper).filter(
                    Paper.pmid.in_(list(missing_pmids))
                ).update(
                    {Paper.embedding_status: EmbeddingStatus.PENDING.value},
                    synchronize_session=False
                )
                
                # EmbeddingTask도 리셋
                db.query(EmbeddingTask).filter(
                    EmbeddingTask.pmid.in_(list(missing_pmids))
                ).update(
                    {EmbeddingTask.status: EmbeddingStatus.PENDING.value},
                    synchronize_session=False
                )
                
                db.commit()
                add_log("info", f"🔄 Synced {len(missing_pmids)} papers: reset to PENDING")
            
            return {
                "synced_count": len(missing_pmids),
                "synced_pmids": list(missing_pmids)[:100],
            }
    
    def reset_all_embeddings(self) -> dict:
        """모든 임베딩 상태를 PENDING으로 초기화 (Force Re-embed)"""
        with get_db_session() as db:
            # Paper 테이블 리셋
            paper_count = db.query(Paper).filter(
                Paper.embedding_status != EmbeddingStatus.PENDING.value
            ).update(
                {Paper.embedding_status: EmbeddingStatus.PENDING.value},
                synchronize_session=False
            )
            
            # EmbeddingTask 테이블 리셋
            task_count = db.query(EmbeddingTask).filter(
                EmbeddingTask.status != EmbeddingStatus.PENDING.value
            ).update(
                {EmbeddingTask.status: EmbeddingStatus.PENDING.value},
                synchronize_session=False
            )
            
            db.commit()
            add_log("warning", f"🔄 Reset all embeddings: {paper_count} papers, {task_count} tasks → PENDING")
            
            return {
                "papers_reset": paper_count,
                "tasks_reset": task_count,
            }


# 싱글톤 인스턴스
embedding_worker = EmbeddingWorker()

