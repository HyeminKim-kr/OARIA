"""pubType 필터링 및 논문 관계 처리

OAR-XX 설계:
- pubTypeList 기반 논문 필터링
- commentCorrectionList 기반 관계 추출
- RAG 품질을 위한 정정/철회 논문 플래그 관리
"""

import re
from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger()


class CollectAction(Enum):
    """수집 행동 결정"""
    COLLECT = "collect"         # 수집 및 임베딩
    STORE_ONLY = "store_only"   # 저장만 (임베딩 X) - Correction/Retraction
    DROP = "drop"               # 완전 제외


class RelationType(Enum):
    """정규화된 관계 타입"""
    RETRACTION = "retraction"
    ERRATUM = "erratum"
    CORRECTION = "correction"
    COMMENT = "comment"


class RelationDirection(Enum):
    """관계 방향"""
    OUTWARD = "outward"  # 현재 문서가 Correction, link.id가 원문
    INWARD = "inward"    # 현재 문서가 원문


@dataclass
class ParsedRelation:
    """파싱된 관계 정보"""
    target_pmid: str           # 관련 논문 PMID
    relation_type: RelationType
    direction: RelationDirection
    raw_type: str              # 원본 문자열
    reference: str = ""        # 참조 문자열


# ============================================================
# 필터링 키워드 정의 (정규화: 소문자 + 부분 매칭)
# ============================================================

# 완전 드랍 (수집하지 않음)
DROP_KEYWORDS = frozenset([
    "editorial",
    "commentary",
    "opinion",
    "news",
    "perspective",
    "letter",           # 초기 제외
    "correspondence",   # 초기 제외
])

# 저장만 (임베딩 하지 않음) - Correction/Retraction 문서
STORE_ONLY_KEYWORDS = frozenset([
    "erratum",
    "corrigendum",
    "correction",
    "retraction",
    "retracted publication",  # 명시적 추가
    "published erratum",      # 명시적 추가
])

# 관계 타입 매핑 (부분 매칭용)
RELATION_TYPE_PATTERNS = [
    (re.compile(r"retract", re.IGNORECASE), RelationType.RETRACTION),
    (re.compile(r"erratum", re.IGNORECASE), RelationType.ERRATUM),
    (re.compile(r"corrigend", re.IGNORECASE), RelationType.CORRECTION),  # corrigendum
    (re.compile(r"correct", re.IGNORECASE), RelationType.CORRECTION),
    (re.compile(r"comment", re.IGNORECASE), RelationType.COMMENT),
]

# 방향 패턴 (단어 경계 사용)
OUTWARD_PATTERN = re.compile(r"\b(for|of|on)\b", re.IGNORECASE)  # 현재 문서 → 원문
INWARD_PATTERN = re.compile(r"\bin\b", re.IGNORECASE)            # 원문 ← 정정 문서


def _normalize_types(pub_types: list[str]) -> list[str]:
    """pubType 정규화 (소문자, 공백 정리)"""
    return [t.lower().strip() for t in pub_types if t]


def _contains_keyword(normalized_types: list[str], keywords: frozenset) -> bool:
    """키워드 포함 여부 (부분 매칭)"""
    for t in normalized_types:
        for kw in keywords:
            if kw in t:
                return True
    return False


def determine_collect_action(pub_types: list[str]) -> CollectAction:
    """pubType 기반 수집 행동 결정

    Args:
        pub_types: Europe PMC pubTypeList에서 추출한 타입 목록

    Returns:
        CollectAction: 수집/저장만/드랍

    규칙:
        1. DROP_KEYWORDS 포함 → DROP (editorial, commentary, ...)
        2. STORE_ONLY_KEYWORDS 포함 → STORE_ONLY (erratum, retraction, ...)
        3. 그 외 → COLLECT (research-article, review, ...)
    """
    if not pub_types:
        return CollectAction.COLLECT

    normalized = _normalize_types(pub_types)

    # 1. 드랍 체크 (우선순위 높음)
    if _contains_keyword(normalized, DROP_KEYWORDS):
        logger.debug("pub_type_drop", pub_types=pub_types)
        return CollectAction.DROP

    # 2. 저장만 체크
    if _contains_keyword(normalized, STORE_ONLY_KEYWORDS):
        logger.debug("pub_type_store_only", pub_types=pub_types)
        return CollectAction.STORE_ONLY

    # 3. 정상 수집
    return CollectAction.COLLECT


def should_collect(pub_types: list[str]) -> bool:
    """수집 여부 결정 (DROP이 아니면 수집)"""
    return determine_collect_action(pub_types) != CollectAction.DROP


def should_embed(pub_types: list[str]) -> bool:
    """임베딩 여부 결정 (COLLECT만 임베딩)"""
    return determine_collect_action(pub_types) == CollectAction.COLLECT


def _parse_relation_type(raw_type: str) -> RelationType:
    """관계 타입 정규화

    Args:
        raw_type: 원본 관계 문자열 (예: "Erratum for", "Retraction of")

    Returns:
        RelationType: 정규화된 관계 타입
    """
    for pattern, rel_type in RELATION_TYPE_PATTERNS:
        if pattern.search(raw_type):
            return rel_type

    # 기본값: comment
    return RelationType.COMMENT


def _parse_relation_direction(raw_type: str) -> RelationDirection:
    """관계 방향 파싱

    Args:
        raw_type: 원본 관계 문자열 (예: "Erratum for", "Erratum in")

    Returns:
        RelationDirection:
            - OUTWARD: "for/of/on" 포함 → 현재 문서가 Correction, target이 원문
            - INWARD: "in" 포함 → 현재 문서가 원문, target이 Correction

    예시:
        - "Erratum for" → OUTWARD (현재=Erratum, target=원문)
        - "Erratum in" → INWARD (현재=원문, target=Erratum)
    """
    # "for/of/on" 먼저 체크 (더 일반적인 케이스)
    if OUTWARD_PATTERN.search(raw_type):
        return RelationDirection.OUTWARD

    # "in" 체크
    if INWARD_PATTERN.search(raw_type):
        return RelationDirection.INWARD

    # 기본값: outward (보수적으로 현재 문서가 정정 문서라고 가정)
    logger.warning("unknown_relation_direction", raw_type=raw_type)
    return RelationDirection.OUTWARD


def parse_comment_correction(
    comment_correction: dict,
    current_pmid: str | None = None,
) -> ParsedRelation | None:
    """commentCorrection 파싱

    Args:
        comment_correction: Europe PMC commentCorrectionList 항목
            {
                "id": "12345678",          # 관련 논문 PMID
                "type": "Erratum for",     # 관계 타입
                "source": "MED",           # 출처
                "reference": "..."         # 참조 문자열
            }
        current_pmid: 현재 문서의 PMID (로깅용)

    Returns:
        ParsedRelation 또는 None (파싱 실패 시)
    """
    target_pmid = comment_correction.get("id")
    raw_type = comment_correction.get("type", "")

    if not target_pmid:
        logger.debug(
            "skip_relation_no_target",
            current_pmid=current_pmid,
            raw_type=raw_type,
        )
        return None

    relation_type = _parse_relation_type(raw_type)
    direction = _parse_relation_direction(raw_type)

    logger.debug(
        "parsed_relation",
        current_pmid=current_pmid,
        target_pmid=target_pmid,
        raw_type=raw_type,
        relation_type=relation_type.value,
        direction=direction.value,
    )

    return ParsedRelation(
        target_pmid=target_pmid,
        relation_type=relation_type,
        direction=direction,
        raw_type=raw_type,
        reference=comment_correction.get("reference", ""),
    )


def get_flag_column(relation_type: RelationType) -> str | None:
    """관계 타입에 해당하는 플래그 컬럼명

    Args:
        relation_type: 관계 타입

    Returns:
        컬럼명 또는 None (comment는 플래그 없음)
    """
    mapping = {
        RelationType.RETRACTION: "has_retraction",
        RelationType.ERRATUM: "has_erratum",
        RelationType.CORRECTION: "has_correction",
        # RelationType.COMMENT → None (플래그 없음)
    }
    return mapping.get(relation_type)
