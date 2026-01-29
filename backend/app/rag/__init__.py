"""RAG 모듈

Strategy Pattern + Registry Pattern으로 모듈화된 RAG 컴포넌트들을 제공합니다.

사용법:
    from app.rag import get_chunker, get_embedder, get_retriever, get_reranker
    from app.rag import list_chunkers, list_embedders, list_retrievers, list_rerankers

    # 전략 목록 조회
    print(list_chunkers())    # ["fixed_size"]
    print(list_rerankers())   # ["bge", "none"]

    # 전략 인스턴스 가져오기
    chunker = get_chunker("fixed_size")
    reranker = get_reranker("bge")

    # 모든 전략 목록
    strategies = get_all_strategies()
"""

# 컴포넌트 import (레지스트리에 자동 등록됨)
from app.rag import chunkers  # noqa: F401
from app.rag import classifiers  # noqa: F401
from app.rag import embedders  # noqa: F401
from app.rag import evaluators  # noqa: F401
from app.rag import retrievers  # noqa: F401
from app.rag import rerankers  # noqa: F401

# 공통 타입
from app.rag.base import (
    Chunk,
    EmbeddingResult,
    SearchResult,
    RerankResult,
    ClassificationResult,
    EvaluationResult,
)

# 레지스트리 함수
from app.rag.registry import (
    # Chunker
    get_chunker,
    list_chunkers,
    get_chunker_info,
    register_chunker,
    # Embedder
    get_embedder,
    list_embedders,
    get_embedder_info,
    register_embedder,
    # Retriever
    get_retriever,
    list_retrievers,
    get_retriever_info,
    register_retriever,
    # Reranker
    get_reranker,
    list_rerankers,
    get_reranker_info,
    register_reranker,
    # Classifier
    get_classifier,
    list_classifiers,
    get_classifier_info,
    register_classifier,
    # Evaluator
    get_evaluator,
    list_evaluators,
    get_evaluator_info,
    register_evaluator,
    # 전체 조회
    get_all_strategies,
    get_all_strategies_info,
)

__all__ = [
    # 공통 타입
    "Chunk",
    "EmbeddingResult",
    "SearchResult",
    "RerankResult",
    "ClassificationResult",
    "EvaluationResult",
    # Chunker
    "get_chunker",
    "list_chunkers",
    "get_chunker_info",
    "register_chunker",
    # Embedder
    "get_embedder",
    "list_embedders",
    "get_embedder_info",
    "register_embedder",
    # Retriever
    "get_retriever",
    "list_retrievers",
    "get_retriever_info",
    "register_retriever",
    # Reranker
    "get_reranker",
    "list_rerankers",
    "get_reranker_info",
    "register_reranker",
    # Classifier
    "get_classifier",
    "list_classifiers",
    "get_classifier_info",
    "register_classifier",
    # Evaluator
    "get_evaluator",
    "list_evaluators",
    "get_evaluator_info",
    "register_evaluator",
    # 전체 조회
    "get_all_strategies",
    "get_all_strategies_info",
]
