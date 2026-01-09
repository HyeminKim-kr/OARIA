"""Lab 라우터

Admin에서 RAG 품질 테스트를 위한 API
- 검색 테스트: 쿼리에 대한 검색 결과 확인
- 답변 생성 테스트: RAG + LLM 답변 생성
- Reranker 테스트: 검색 결과 재정렬
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import RAGStrategy
from app.services import rag_service, llm_service
from app.services.embedding_service import embedding_service
from app.services.weaviate_service import weaviate_service
from app.services.reranker_service import reranker_service
from app.rag import (
    get_all_strategies,
    get_chunker_info,
    get_embedder_info,
    get_retriever_info,
    get_reranker_info,
    get_reranker,
)


router = APIRouter(prefix="/lab", tags=["lab"])


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────


class SearchTestRequest(BaseModel):
    """검색 테스트 요청"""

    query: str = Field(..., description="검색 쿼리")
    limit: int = Field(default=10, ge=1, le=50, description="검색 결과 개수")
    alpha: float = Field(default=0.7, ge=0, le=1, description="하이브리드 검색 가중치")
    use_reranker: bool = Field(default=False, description="Reranker 사용 여부")
    reranker: str | None = Field(default="bge", description="Reranker 전략 (예: bge, none)")
    min_rerank_score: float | None = Field(default=None, ge=0, le=1, description="Reranker 최소 점수 임계값")
    collection_name: str | None = Field(default=None, description="Weaviate 컬렉션 이름 (샘플 임베딩용, None이면 기본 컬렉션)")


class ChunkResult(BaseModel):
    """검색된 청크"""

    paper_id: str
    paper_title: str
    section_name: str
    chunk_index: int
    content: str
    score: float
    rerank_score: float | None = None  # Reranker 점수
    original_score: float | None = None  # 원본 벡터 검색 점수
    metadata: dict[str, Any] | None = None


class SearchTestResponse(BaseModel):
    """검색 테스트 응답"""

    query: str
    chunks: list[ChunkResult]
    search_latency_ms: int
    rerank_latency_ms: int | None = None  # Reranker 소요 시간
    total_chunks: int
    parameters: dict[str, Any]


class GenerateTestRequest(BaseModel):
    """답변 생성 테스트 요청"""

    query: str = Field(..., description="질문")
    limit: int = Field(default=5, ge=1, le=20, description="검색 결과 개수")
    alpha: float = Field(default=0.7, ge=0, le=1, description="하이브리드 검색 가중치")
    use_reranker: bool = Field(default=False, description="Reranker 사용 여부")
    reranker: str | None = Field(default="bge", description="Reranker 전략 (예: bge, none)")
    collection_name: str | None = Field(default=None, description="Weaviate 컬렉션 이름 (샘플 임베딩용, None이면 기본 컬렉션)")


class ReferenceResult(BaseModel):
    """참조 결과"""

    paper_id: str
    title: str
    section: str
    content: str
    score: float


class GenerateTestResponse(BaseModel):
    """답변 생성 테스트 응답"""

    query: str
    answer: str
    references: list[ReferenceResult]
    search_latency_ms: int
    rerank_latency_ms: int | None = None
    llm_latency_ms: int
    total_latency_ms: int
    model: str
    tokens_used: dict[str, int] | None = None
    use_reranker: bool = False


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.post("/search", response_model=SearchTestResponse)
def test_search(request: SearchTestRequest):
    """RAG 검색 테스트

    쿼리에 대한 검색 결과(청크)를 반환합니다.
    검색 파라미터를 조정하여 품질을 테스트할 수 있습니다.
    Reranker를 사용하면 더 정확한 관련성 점수를 얻을 수 있습니다.
    """
    start = time.perf_counter()
    rerank_latency_ms = None

    try:
        # 1. 쿼리 임베딩
        query_vector = embedding_service.embed_text(request.query)

        # 2. 하이브리드 검색 (Reranker 사용 시 더 많이 가져옴)
        search_limit = request.limit * 3 if request.use_reranker else request.limit

        results = weaviate_service.search_hybrid(
            query=request.query,
            query_vector=query_vector,
            limit=search_limit,
            alpha=request.alpha,
            collection_name=request.collection_name,
        )

        # 3. Reranker로 재정렬 (선택적)
        reranker_name = request.reranker or "bge"
        if request.use_reranker and results and reranker_name != "none":
            rerank_start = time.perf_counter()

            # 선택한 reranker 전략 사용
            reranker = get_reranker(reranker_name)
            rerank_results = reranker.rerank(
                query=request.query,
                documents=results,
                top_k=request.limit,
            )

            # Rerank 결과로 교체
            results = []
            for rr in rerank_results:
                doc = rr.document.copy()
                doc["rerank_score"] = rr.score
                doc["original_score"] = doc.get("score", 0.0)
                doc["score"] = rr.score
                results.append(doc)

            rerank_latency_ms = int((time.perf_counter() - rerank_start) * 1000)

        # 4. 결과 변환
        chunks = []
        for r in results:
            chunks.append(
                ChunkResult(
                    paper_id=r.get("paperId", ""),
                    paper_title=r.get("title", ""),
                    section_name=r.get("section", ""),
                    chunk_index=r.get("chunkIndex", 0),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                    rerank_score=r.get("rerank_score"),
                    original_score=r.get("original_score"),
                    metadata={
                        "year": r.get("year"),
                        "journal": r.get("journal"),
                        "offset_start": r.get("offsetStart"),
                        "offset_end": r.get("offsetEnd"),
                    },
                )
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return SearchTestResponse(
            query=request.query,
            chunks=chunks,
            search_latency_ms=elapsed_ms,
            rerank_latency_ms=rerank_latency_ms,
            total_chunks=len(chunks),
            parameters={
                "limit": request.limit,
                "alpha": request.alpha,
                "use_reranker": request.use_reranker,
                "reranker": reranker_name if request.use_reranker else None,
                "min_rerank_score": request.min_rerank_score,
                "reranker_model": reranker_name if request.use_reranker else None,
                "collection_name": request.collection_name,
            },
        )

    except Exception as e:
        error_msg = str(e)

        # Weaviate 스키마 없음 (임베딩 데이터 없음)
        if "could not find class" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "no_embedding_data",
                    "message": "임베딩된 논문이 없습니다. Papers 페이지에서 논문을 수집하고 임베딩을 실행해주세요.",
                },
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {error_msg}",
        )


@router.get("/reranker/status")
def get_reranker_status():
    """Reranker 서비스 상태 확인"""
    return reranker_service.get_status()


# ─────────────────────────────────────────────────────────────
# Strategies API
# ─────────────────────────────────────────────────────────────


class StrategyInfo(BaseModel):
    """전략 정보"""

    name: str
    class_name: str
    module: str
    description: str
    config: dict[str, Any] | None = None


class StrategiesResponse(BaseModel):
    """사용 가능한 전략 목록"""

    chunkers: list[str]
    embedders: list[str]
    retrievers: list[str]
    rerankers: list[str]
    classifiers: list[str]
    evaluators: list[str]


class StrategiesDetailResponse(BaseModel):
    """전략 상세 정보"""

    chunkers: list[StrategyInfo]
    embedders: list[StrategyInfo]
    retrievers: list[StrategyInfo]
    rerankers: list[StrategyInfo]


@router.get("/strategies", response_model=StrategiesResponse)
def get_strategies():
    """사용 가능한 RAG 전략 목록

    Admin Lab에서 드롭다운 선택을 위해 등록된 전략 이름들을 반환합니다.
    """
    return get_all_strategies()


@router.get("/strategies/detail", response_model=StrategiesDetailResponse)
def get_strategies_detail():
    """RAG 전략 상세 정보

    각 전략의 클래스명, 설명, 현재 설정값을 포함합니다.
    """
    return {
        "chunkers": get_chunker_info(),
        "embedders": get_embedder_info(),
        "retrievers": get_retriever_info(),
        "rerankers": get_reranker_info(),
    }


# ─────────────────────────────────────────────────────────────
# DB 기반 전략 조회 API
# ─────────────────────────────────────────────────────────────


class DBStrategyInfo(BaseModel):
    """DB 저장 전략 정보"""

    id: str
    category: str
    name: str
    description: str | None
    config: dict[str, Any] | None
    location: str  # backend or batch
    is_active: bool


class DBStrategiesResponse(BaseModel):
    """DB에서 조회한 전략 목록"""

    chunkers: list[DBStrategyInfo]
    embedders: list[DBStrategyInfo]
    retrievers: list[DBStrategyInfo]
    rerankers: list[DBStrategyInfo]


@router.get("/strategies/db", response_model=DBStrategiesResponse)
async def get_strategies_from_db(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """DB에서 RAG 전략 조회

    서버 시작 시 코드에서 동기화된 전략 정보를 DB에서 조회합니다.
    Batch(청킹, 임베딩)와 Backend(검색, 리랭킹) 전략 모두 포함됩니다.

    Args:
        active_only: True면 활성 전략만 반환 (기본값: True)
    """
    query = select(RAGStrategy)
    if active_only:
        query = query.where(RAGStrategy.is_active == True)
    query = query.order_by(RAGStrategy.category, RAGStrategy.name)

    result = await db.execute(query)
    strategies = result.scalars().all()

    # 카테고리별 분류
    response: dict[str, list[DBStrategyInfo]] = {
        "chunkers": [],
        "embedders": [],
        "retrievers": [],
        "rerankers": [],
    }

    category_map = {
        "chunker": "chunkers",
        "embedder": "embedders",
        "retriever": "retrievers",
        "reranker": "rerankers",
    }

    for s in strategies:
        key = category_map.get(s.category)
        if key:
            response[key].append(
                DBStrategyInfo(
                    id=str(s.id),
                    category=s.category,
                    name=s.name,
                    description=s.description,
                    config=s.config,
                    location=s.location,
                    is_active=s.is_active,
                )
            )

    return response


# ─────────────────────────────────────────────────────────────
# Sample Embedding Trigger API
# ─────────────────────────────────────────────────────────────


class TriggerSampleEmbedRequest(BaseModel):
    """샘플 임베딩 트리거 요청"""

    embedding_id: str = Field(..., description="sample_embeddings 테이블 ID")


class TriggerSampleEmbedResponse(BaseModel):
    """샘플 임베딩 트리거 응답"""

    success: bool
    task_id: str | None = None
    message: str


def _get_redis_client():
    """Redis 클라이언트 생성"""
    import os
    import redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)


@router.post("/sample-embed/trigger", response_model=TriggerSampleEmbedResponse)
def trigger_sample_embed(request: TriggerSampleEmbedRequest):
    """샘플 임베딩 작업 생성 (V2 - JobStateManager 사용)

    Admin에서 임베딩 생성 요청 시 호출됩니다.
    Redis에 작업을 등록하고, Celery Beat가 dispatch합니다.
    """
    try:
        redis_client = _get_redis_client()
        job_id = request.embedding_id
        job_type = "embed"

        # Redis에 작업 상태 등록
        state_key = f"job:{job_type}:{job_id}:state"
        queue_key = f"queue:{job_type}:pending"

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        state = {
            "status": "queued",
            "progress": 0,
            "total": 0,
            "retry_count": 0,
            "error": "",
            "worker_id": "",
            "created_at": now,
            "queued_at": now,
            "started_at": "",
            "completed_at": "",
            "heartbeat": "",
        }

        # 상태 저장 + 큐에 추가
        pipe = redis_client.pipeline()
        pipe.hset(state_key, mapping=state)
        pipe.rpush(queue_key, job_id)
        pipe.execute()

        return TriggerSampleEmbedResponse(
            success=True,
            task_id=None,  # Beat가 dispatch할 예정
            message=f"Job queued for processing: {job_id}",
        )

    except Exception as e:
        return TriggerSampleEmbedResponse(
            success=False,
            task_id=None,
            message=f"Failed to queue job: {str(e)}",
        )


@router.post("/sample-embed/delete", response_model=TriggerSampleEmbedResponse)
def trigger_sample_embed_delete(request: TriggerSampleEmbedRequest):
    """샘플 임베딩 삭제 Celery 태스크 트리거

    Admin에서 임베딩 삭제 요청 시 호출됩니다.
    """
    try:
        from celery import Celery
        import os

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        celery_app = Celery(
            "oaria_batch",
            broker=redis_url,
            backend=redis_url,
        )

        task = celery_app.send_task(
            "src.tasks.sample_embed.delete_sample_embed",
            args=[request.embedding_id],
            queue="embed",
        )

        # Redis에서 작업 상태 삭제
        try:
            redis_client = _get_redis_client()
            job_type = "embed"
            redis_client.delete(
                f"job:{job_type}:{request.embedding_id}:state",
                f"job:{job_type}:{request.embedding_id}:lock",
            )
        except Exception:
            pass  # Redis 삭제 실패해도 계속 진행

        return TriggerSampleEmbedResponse(
            success=True,
            task_id=task.id,
            message=f"Sample embedding delete task triggered: {task.id}",
        )

    except Exception as e:
        return TriggerSampleEmbedResponse(
            success=False,
            task_id=None,
            message=f"Failed to trigger delete task: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# V2 Job Management API
# ─────────────────────────────────────────────────────────────


class JobStatusResponse(BaseModel):
    """작업 상태 응답 (Redis에서 실시간 조회)"""

    job_id: str
    status: str
    progress: int
    total: int
    retry_count: int
    error: str | None
    worker_id: str | None
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    heartbeat: str | None


@router.get("/sample-embed/{embedding_id}/status", response_model=JobStatusResponse)
def get_sample_embed_status(embedding_id: str):
    """샘플 임베딩 작업 실시간 상태 조회 (Redis)

    Redis에서 작업 상태를 조회합니다. DB보다 더 실시간 정보를 제공합니다.
    """
    try:
        redis_client = _get_redis_client()
        job_type = "embed"
        state_key = f"job:{job_type}:{embedding_id}:state"

        state = redis_client.hgetall(state_key)

        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found in Redis: {embedding_id}",
            )

        return JobStatusResponse(
            job_id=embedding_id,
            status=state.get("status", "unknown"),
            progress=int(state.get("progress", 0)),
            total=int(state.get("total", 0)),
            retry_count=int(state.get("retry_count", 0)),
            error=state.get("error") or None,
            worker_id=state.get("worker_id") or None,
            created_at=state.get("created_at") or None,
            started_at=state.get("started_at") or None,
            completed_at=state.get("completed_at") or None,
            heartbeat=state.get("heartbeat") or None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}",
        )


@router.post("/sample-embed/{embedding_id}/retry", response_model=TriggerSampleEmbedResponse)
def retry_sample_embed(embedding_id: str):
    """샘플 임베딩 작업 재시도

    실패하거나 stuck된 작업을 재시도합니다.
    최대 재시도 횟수(3회)를 초과하면 실패합니다.
    """
    MAX_RETRIES = 3

    try:
        redis_client = _get_redis_client()
        job_type = "embed"
        state_key = f"job:{job_type}:{embedding_id}:state"
        queue_key = f"queue:{job_type}:pending"
        lock_key = f"job:{job_type}:{embedding_id}:lock"

        state = redis_client.hgetall(state_key)

        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {embedding_id}",
            )

        current_status = state.get("status", "")
        retry_count = int(state.get("retry_count", 0))

        # 이미 완료된 작업은 재시도 불가
        if current_status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry a completed job",
            )

        # 최대 재시도 초과
        if retry_count >= MAX_RETRIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Max retries exceeded ({MAX_RETRIES})",
            )

        # 상태 업데이트 + 큐에 추가
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        pipe = redis_client.pipeline()
        pipe.hset(state_key, mapping={
            "status": "queued",
            "queued_at": now,
            "error": "",
            "worker_id": "",
        })
        pipe.rpush(queue_key, embedding_id)
        pipe.delete(lock_key)  # 기존 락 제거
        pipe.execute()

        return TriggerSampleEmbedResponse(
            success=True,
            task_id=None,
            message=f"Job queued for retry (attempt {retry_count + 1}/{MAX_RETRIES})",
        )

    except HTTPException:
        raise
    except Exception as e:
        return TriggerSampleEmbedResponse(
            success=False,
            task_id=None,
            message=f"Failed to retry job: {str(e)}",
        )


@router.post("/sample-embed/{embedding_id}/cancel", response_model=TriggerSampleEmbedResponse)
def cancel_sample_embed(embedding_id: str):
    """샘플 임베딩 작업 취소

    대기 중이거나 처리 중인 작업을 취소합니다.
    이미 완료된 작업은 취소할 수 없습니다.
    """
    try:
        redis_client = _get_redis_client()
        job_type = "embed"
        state_key = f"job:{job_type}:{embedding_id}:state"
        lock_key = f"job:{job_type}:{embedding_id}:lock"

        state = redis_client.hgetall(state_key)

        if not state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {embedding_id}",
            )

        current_status = state.get("status", "")

        # 이미 완료된 작업은 취소 불가
        if current_status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a completed job",
            )

        # 상태를 cancelled로 변경
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        pipe = redis_client.pipeline()
        pipe.hset(state_key, mapping={
            "status": "cancelled",
            "cancelled_at": now,
        })
        pipe.delete(lock_key)  # 락 해제
        pipe.execute()

        return TriggerSampleEmbedResponse(
            success=True,
            task_id=None,
            message=f"Job cancelled: {embedding_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        return TriggerSampleEmbedResponse(
            success=False,
            task_id=None,
            message=f"Failed to cancel job: {str(e)}",
        )


@router.post("/generate", response_model=GenerateTestResponse)
def test_generate(request: GenerateTestRequest):
    """RAG + LLM 답변 생성 테스트

    검색 후 LLM으로 답변을 생성합니다.
    Reranker를 사용하면 더 관련성 높은 문서로 답변을 생성합니다.
    """
    total_start = time.perf_counter()

    try:
        # 1. RAG 검색 (Reranker 옵션 포함)
        retrieval_result = rag_service.retrieve(
            query=request.query,
            use_reranker=request.use_reranker,
            collection_name=request.collection_name,
        )

        search_latency_ms = retrieval_result.search_latency_ms
        rerank_latency_ms = retrieval_result.rerank_latency_ms
        llm_start = time.perf_counter()

        # 2. LLM 답변 생성 (스트리밍 대신 전체 응답)
        full_content = ""
        usage = None

        for chunk in llm_service.generate_stream(
            question=request.query,
            context=retrieval_result.context,
            references=retrieval_result.references,
        ):
            if chunk.is_done:
                usage = chunk.usage
            elif chunk.token:
                full_content += chunk.token

        llm_latency_ms = int((time.perf_counter() - llm_start) * 1000)
        total_latency_ms = int((time.perf_counter() - total_start) * 1000)

        # 3. References 변환
        references = []
        for ref in retrieval_result.references:
            references.append(
                ReferenceResult(
                    paper_id=ref.paper_id,
                    title=ref.title,
                    section=ref.section,
                    content=ref.snippet,
                    score=ref.distance,
                )
            )

        return GenerateTestResponse(
            query=request.query,
            answer=full_content,
            references=references,
            search_latency_ms=search_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            llm_latency_ms=llm_latency_ms,
            total_latency_ms=total_latency_ms,
            model="gpt-4o-mini" if not llm_service.use_mock else "mock",
            tokens_used={
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
            } if usage else None,
            use_reranker=request.use_reranker,
        )

    except Exception as e:
        error_msg = str(e)

        # Weaviate 스키마 없음 (임베딩 데이터 없음)
        if "could not find class" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "no_embedding_data",
                    "message": "임베딩된 논문이 없습니다. Papers 페이지에서 논문을 수집하고 임베딩을 실행해주세요.",
                },
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generate failed: {error_msg}",
        )
