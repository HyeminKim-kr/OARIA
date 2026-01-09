"""RAG 공통 타입 정의"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """청킹 결과"""

    content: str
    index: int
    offset_start: int
    offset_end: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResult:
    """임베딩 결과"""

    vector: list[float]
    model: str
    dimensions: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """검색 결과"""

    content: str
    score: float
    paper_id: str
    chunk_id: str
    title: str
    section: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RerankResult:
    """리랭킹 결과"""

    index: int
    score: float
    document: dict[str, Any]
    original_score: float | None = None


@dataclass
class ClassificationResult:
    """분류 결과"""

    category: str  # oncology, cardiology, etc.
    confidence: float
    is_allowed: bool  # oncology면 True
    reason: str | None = None


@dataclass
class EvaluationResult:
    """품질 평가 결과"""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    overall_score: float | None = None
    passed: bool = True
    details: dict[str, Any] = field(default_factory=dict)
