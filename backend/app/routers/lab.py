"""Lab 라우터

Admin에서 RAG 품질 테스트를 위한 API
- 검색 테스트: 쿼리에 대한 검색 결과 확인
- 답변 생성 테스트: RAG + LLM 답변 생성
- Reranker 테스트: 검색 결과 재정렬
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services import rag_service, llm_service
from app.services.embedding_service import embedding_service
from app.services.weaviate_service import weaviate_service
from app.services.reranker_service import reranker_service


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
    min_rerank_score: float | None = Field(default=None, ge=0, le=1, description="Reranker 최소 점수 임계값")


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
        )

        # 3. Reranker로 재정렬 (선택적)
        if request.use_reranker and results:
            rerank_start = time.perf_counter()

            rerank_results = reranker_service.rerank(
                query=request.query,
                documents=results,
                content_key="content",
                top_k=request.limit,
                min_score=request.min_rerank_score,
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
                "min_rerank_score": request.min_rerank_score,
                "reranker_model": reranker_service.model_name if request.use_reranker else None,
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
