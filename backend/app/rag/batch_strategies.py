"""Batch RAG 전략 정적 정의

Batch (Celery 워커)에서 실행되는 청킹/임베딩 전략의 정보를 정의합니다.
실제 구현은 batch/src/rag/에 있으며, 여기는 정보만 정의합니다.

서버 시작 시 이 정보가 DB에 동기화됩니다.
"""

from typing import Any, Dict, List, TypedDict


class StrategyInfo(TypedDict):
    """전략 정보 타입"""
    name: str
    description: str
    config: Dict[str, Any]


# ============================================================
# Batch Chunkers (인덱싱 시점)
# ============================================================

BATCH_CHUNKERS: List[StrategyInfo] = [
    {
        "name": "fixed_char_1000_200",
        "description": """고정 크기 문자 기반 청킹 (1000자 + 200자 오버랩)

텍스트를 1000자 단위로 분할하고 200자씩 오버랩합니다.
섹션 경계를 고려하지 않아 문맥이 끊길 수 있지만 처리가 빠릅니다.
A/B 테스트에서 semantic 청킹과 비교할 때 baseline으로 사용합니다.

파라미터:
- chunk_size: 1000자 (청크 크기)
- overlap: 200자 (오버랩)""",
        "config": {
            "chunk_size": 1000,
            "overlap": 200,
        },
    },
    {
        "name": "semantic_section_700t",
        "description": """섹션 기반 시맨틱 청킹 (700토큰, Recursive)

논문의 섹션 구조(Abstract, Methods, Results 등)를 존중합니다.
섹션 내에서 700토큰을 초과하면 문단 > 줄바꿈 > 문장 순으로 분할합니다.
섹션 경계에서 문맥이 끊기지 않아 검색 품질이 높습니다.

파라미터:
- chunk_size_tokens: 700 (목표 청크 크기)
- overlap_tokens: 100 (오버랩)
- separators: ["\\n\\n", "\\n", ". ", " "]""",
        "config": {
            "chunk_size_tokens": 700,
            "overlap_tokens": 100,
        },
    },
]


# ============================================================
# Batch Embedders (인덱싱 시점)
# ============================================================

BATCH_EMBEDDERS: List[StrategyInfo] = [
    {
        "name": "openai_3small",
        "description": """OpenAI text-embedding-3-small (1536차원)

비용 효율적인 임베딩 모델입니다.
대부분의 RAG 사용 케이스에 적합합니다.
비용: $0.02 / 1M tokens

파라미터:
- model: text-embedding-3-small
- dimension: 1536""",
        "config": {
            "model": "text-embedding-3-small",
            "dimension": 1536,
        },
    },
    {
        "name": "openai_3large",
        "description": """OpenAI text-embedding-3-large (3072차원)

고품질 임베딩 모델입니다.
더 정밀한 의미 표현이 필요한 경우 사용합니다.
비용: $0.13 / 1M tokens (small 대비 6.5배)

파라미터:
- model: text-embedding-3-large
- dimension: 3072""",
        "config": {
            "model": "text-embedding-3-large",
            "dimension": 3072,
        },
    },
]


# ============================================================
# 전체 Batch 전략
# ============================================================

def get_all_batch_strategies() -> Dict[str, List[StrategyInfo]]:
    """모든 Batch 전략 정보 반환"""
    return {
        "chunker": BATCH_CHUNKERS,
        "embedder": BATCH_EMBEDDERS,
    }
