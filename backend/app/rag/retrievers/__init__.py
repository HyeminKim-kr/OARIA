"""검색 전략 모듈

사용 가능한 전략:
- hybrid_alpha70: 하이브리드 검색 (벡터 70% + BM25 30%, 프로덕션 사용)
- dense: Dense 벡터 검색만 (TODO)
"""

from .base import RetrieverProtocol
from .hybrid import HybridAlpha70Retriever

__all__ = [
    "RetrieverProtocol",
    "HybridAlpha70Retriever",
]
