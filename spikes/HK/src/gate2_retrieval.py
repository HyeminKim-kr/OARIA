"""
Gate 2: Retrieval Confidence Validation

Validates retrieval quality before generating answers:
- OAR-37: Similarity Threshold (max score ≥ 0.7)
- OAR-38: Minimum Relevant Docs (≥3 docs with score ≥ 0.6)
- OAR-39: Domain Validation (≥80% oncology domain)
- OAR-40: Integration API combining all checks

Author: HK
Created: 2025-12-30
Jira: OAR-37, OAR-38, OAR-39, OAR-40
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import logging

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Gate2Config:
    """
    Configuration for Gate 2 validation thresholds.

    All thresholds are configurable to allow tuning based on:
    - Domain-specific requirements
    - Quality vs coverage tradeoffs
    - User experience preferences
    """
    # OAR-37: Similarity threshold
    similarity_threshold: float = 0.7

    # OAR-38: Minimum relevant documents
    min_relevant_docs: int = 3
    min_doc_score: float = 0.6

    # OAR-39: Domain validation
    domain_ratio_threshold: float = 0.80  # 80%

    # Oncology-related keywords for domain detection
    oncology_keywords: list[str] = field(default_factory=lambda: [
        # General cancer terms
        "cancer", "tumor", "tumour", "oncology", "malignant", "neoplasm",
        "carcinoma", "sarcoma", "lymphoma", "leukemia", "melanoma",
        "metastasis", "metastatic",
        # Treatments
        "chemotherapy", "immunotherapy", "radiation", "targeted therapy",
        "checkpoint inhibitor", "car-t", "car t",
        # Specific cancers
        "lung cancer", "breast cancer", "prostate cancer", "colorectal",
        "pancreatic", "ovarian", "bladder", "kidney", "liver cancer",
        "glioblastoma", "nsclc", "sclc",
        # Biomarkers and genes
        "egfr", "brca", "tp53", "kras", "her2", "pd-l1", "pd-1",
        "alk", "ros1", "braf", "ntrk", "msi", "tmb",
        # Drugs
        "erlotinib", "gefitinib", "osimertinib", "pembrolizumab",
        "nivolumab", "trastuzumab", "bevacizumab", "rituximab",
        # Korean terms
        "암", "종양", "항암", "폐암", "유방암", "위암", "대장암",
        "간암", "췌장암", "전이", "면역치료", "표적치료",
    ])


# Default configuration
DEFAULT_CONFIG = Gate2Config()


# ============================================================================
# RESULT TYPES
# ============================================================================

class Gate2FailureReason(Enum):
    """Enumeration of Gate 2 failure reasons."""
    LOW_SIMILARITY = "low_similarity"
    INSUFFICIENT_DOCS = "insufficient_docs"
    DOMAIN_MISMATCH = "domain_mismatch"


@dataclass
class Gate2Result:
    """
    Result of Gate 2 validation.

    Attributes:
        passed: Whether all validations passed
        reason: Failure reason if not passed
        message: User-friendly message
        max_similarity: Highest similarity score found
        relevant_count: Number of docs above min threshold
        domain_ratio: Ratio of oncology documents
        details: Additional validation details
    """
    passed: bool
    reason: Optional[Gate2FailureReason] = None
    message: str = ""

    # Metrics
    max_similarity: float = 0.0
    relevant_count: int = 0
    domain_ratio: float = 0.0

    # Detailed breakdown
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason.value if self.reason else None,
            "message": self.message,
            "max_similarity": self.max_similarity,
            "relevant_count": self.relevant_count,
            "domain_ratio": self.domain_ratio,
            "details": self.details,
        }


# ============================================================================
# OAR-37: SIMILARITY THRESHOLD VALIDATION
# ============================================================================

def check_similarity_threshold(
    documents: list[dict],
    threshold: float = None,
    config: Gate2Config = None,
) -> tuple[bool, float, str]:
    """
    OAR-37: Check if max similarity score meets threshold.

    Validates that at least one document has a similarity score
    above the threshold, indicating relevant results were found.

    Args:
        documents: List of retrieved documents with 'score' field
        threshold: Override threshold (default from config)
        config: Gate2Config instance

    Returns:
        Tuple of (passed, max_score, message)

    Design Decision:
    ----------------
    We check MAX similarity rather than AVERAGE because:
    - One highly relevant document may be sufficient
    - Average is skewed by noise in lower-ranked results
    - Users care most about the best match

    Example:
        docs = [{"score": 0.85}, {"score": 0.72}, {"score": 0.45}]
        passed, score, msg = check_similarity_threshold(docs)
        # passed=True, score=0.85
    """
    config = config or DEFAULT_CONFIG
    threshold = threshold if threshold is not None else config.similarity_threshold

    if not documents:
        logger.warning("gate2_similarity: No documents to check")
        return False, 0.0, "검색 결과가 없습니다."

    # Extract scores
    scores = []
    for doc in documents:
        score = doc.get("score") or doc.get("rerank_score") or doc.get("similarity", 0)
        scores.append(float(score))

    max_score = max(scores) if scores else 0.0
    passed = max_score >= threshold

    logger.info(
        "gate2_similarity_check",
        max_score=max_score,
        threshold=threshold,
        passed=passed,
    )

    if passed:
        message = f"유사도 검증 통과 (최대 점수: {max_score:.2f})"
    else:
        message = "관련 논문을 충분히 찾지 못했습니다. 질문을 더 구체적으로 해주세요."

    return passed, max_score, message


# ============================================================================
# OAR-38: MINIMUM RELEVANT DOCUMENTS VALIDATION
# ============================================================================

def check_min_relevant_docs(
    documents: list[dict],
    min_count: int = None,
    min_score: float = None,
    config: Gate2Config = None,
) -> tuple[bool, int, str]:
    """
    OAR-38: Check if enough relevant documents were found.

    Validates that a minimum number of documents have similarity
    scores above a secondary threshold.

    Args:
        documents: List of retrieved documents
        min_count: Override minimum count
        min_score: Override minimum score threshold
        config: Gate2Config instance

    Returns:
        Tuple of (passed, relevant_count, message)

    Design Decision:
    ----------------
    Why check count of relevant docs?
    - Multiple sources strengthen confidence in answer
    - Prevents over-reliance on single document
    - Ensures answer can be cross-validated

    Why 0.6 threshold for "relevant"?
    - Lower than main threshold (0.7) to catch borderline relevant docs
    - High enough to exclude noise
    - Empirically tuned for oncology domain

    Example:
        docs = [{"score": 0.85}, {"score": 0.72}, {"score": 0.65}, {"score": 0.45}]
        passed, count, msg = check_min_relevant_docs(docs)
        # passed=True, count=3 (three docs >= 0.6)
    """
    config = config or DEFAULT_CONFIG
    min_count = min_count if min_count is not None else config.min_relevant_docs
    min_score = min_score if min_score is not None else config.min_doc_score

    if not documents:
        logger.warning("gate2_min_docs: No documents to check")
        return False, 0, "검색 결과가 없습니다."

    # Count documents above threshold
    relevant_count = 0
    for doc in documents:
        score = doc.get("score") or doc.get("rerank_score") or doc.get("similarity", 0)
        if float(score) >= min_score:
            relevant_count += 1

    passed = relevant_count >= min_count

    logger.info(
        "gate2_min_docs_check",
        relevant_count=relevant_count,
        min_count=min_count,
        min_score=min_score,
        passed=passed,
    )

    if passed:
        message = f"관련 문서 수 검증 통과 ({relevant_count}개 문서)"
    else:
        message = "충분한 근거 논문을 찾지 못했습니다."

    return passed, relevant_count, message


# ============================================================================
# OAR-39: DOMAIN VALIDATION
# ============================================================================

def check_document_domain(
    text: str,
    keywords: list[str] = None,
    config: Gate2Config = None,
) -> bool:
    """
    Check if a single document belongs to oncology domain.

    Args:
        text: Document text content
        keywords: Override keyword list
        config: Gate2Config instance

    Returns:
        True if document appears to be oncology-related

    Design Decision:
    ----------------
    Simple keyword matching vs ML classifier:
    - Keywords are fast (<1ms) vs classifier (~50ms)
    - Keywords are interpretable and debuggable
    - For Gate 2, speed is critical (runs on every query)
    - ML classifier could be added for edge cases
    """
    config = config or DEFAULT_CONFIG
    keywords = keywords or config.oncology_keywords

    if not text:
        return False

    text_lower = text.lower()

    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True

    return False


def check_domain_validation(
    documents: list[dict],
    threshold: float = None,
    config: Gate2Config = None,
) -> tuple[bool, float, str]:
    """
    OAR-39: Check if retrieved documents are in oncology domain.

    Validates that a sufficient ratio of retrieved documents
    are related to oncology/cancer research.

    Args:
        documents: List of retrieved documents with 'text' field
        threshold: Override domain ratio threshold
        config: Gate2Config instance

    Returns:
        Tuple of (passed, domain_ratio, message)

    Design Decision:
    ----------------
    Why check domain ratio?
    - Even with good similarity, off-topic docs may be retrieved
    - Ensures answer stays within oncology scope
    - Prevents hallucination about non-cancer topics

    Why 80% threshold?
    - Allows some borderline documents
    - High enough to ensure majority are on-topic
    - Empirically determined from test queries

    Example:
        docs = [
            {"text": "EGFR mutations in lung cancer..."},
            {"text": "Immunotherapy for melanoma..."},
            {"text": "General medical advice..."},  # Off-topic
        ]
        passed, ratio, msg = check_domain_validation(docs)
        # passed=False, ratio=0.67 (2/3)
    """
    config = config or DEFAULT_CONFIG
    threshold = threshold if threshold is not None else config.domain_ratio_threshold

    if not documents:
        logger.warning("gate2_domain: No documents to check")
        return False, 0.0, "검색 결과가 없습니다."

    # Check each document
    oncology_count = 0
    for doc in documents:
        text = doc.get("text", "")
        # Also check metadata if available
        metadata = doc.get("metadata", {})
        title = metadata.get("title", "")
        combined_text = f"{title} {text}"

        if check_document_domain(combined_text, config=config):
            oncology_count += 1

    domain_ratio = oncology_count / len(documents) if documents else 0.0
    passed = domain_ratio >= threshold

    logger.info(
        "gate2_domain_check",
        oncology_count=oncology_count,
        total_docs=len(documents),
        domain_ratio=domain_ratio,
        threshold=threshold,
        passed=passed,
    )

    if passed:
        message = f"도메인 검증 통과 (암 연구 비율: {domain_ratio:.0%})"
    else:
        message = "검색 결과가 암 연구와 관련성이 낮습니다."

    return passed, domain_ratio, message


# ============================================================================
# OAR-40: GATE 2 INTEGRATION API
# ============================================================================

def check_retrieval_confidence(
    query: str,
    documents: list[dict],
    config: Gate2Config = None,
) -> Gate2Result:
    """
    OAR-40: Complete Gate 2 validation combining all checks.

    Runs all Gate 2 validations in optimized order and returns
    a comprehensive result.

    Args:
        query: User's query (for logging)
        documents: Retrieved documents to validate
        config: Gate2Config instance

    Returns:
        Gate2Result with pass/fail status and details

    Design Decision:
    ----------------
    Validation order is optimized for fast failure:
    1. Similarity threshold - fastest, most likely to fail for bad queries
    2. Min relevant docs - fast, catches sparse results
    3. Domain validation - slowest, most expensive

    This ordering minimizes average validation time.

    Example:
        result = check_retrieval_confidence("EGFR inhibitors?", docs)
        if not result.passed:
            return error_response(result.message)
    """
    config = config or DEFAULT_CONFIG

    logger.info(
        "gate2_validation_start",
        query=query[:100],
        num_docs=len(documents),
    )

    # Handle empty documents
    if not documents:
        return Gate2Result(
            passed=False,
            reason=Gate2FailureReason.INSUFFICIENT_DOCS,
            message="검색 결과가 없습니다. 다른 키워드로 검색해 보세요.",
            max_similarity=0.0,
            relevant_count=0,
            domain_ratio=0.0,
            details={"query": query},
        )

    # Step 1: Similarity threshold (OAR-37)
    sim_passed, max_sim, sim_msg = check_similarity_threshold(
        documents, config=config
    )

    if not sim_passed:
        logger.warning(
            "gate2_failed",
            reason="low_similarity",
            max_similarity=max_sim,
            query=query[:100],
        )
        return Gate2Result(
            passed=False,
            reason=Gate2FailureReason.LOW_SIMILARITY,
            message=sim_msg,
            max_similarity=max_sim,
            relevant_count=0,
            domain_ratio=0.0,
            details={
                "threshold": config.similarity_threshold,
                "max_score": max_sim,
            },
        )

    # Step 2: Minimum relevant docs (OAR-38)
    docs_passed, relevant_count, docs_msg = check_min_relevant_docs(
        documents, config=config
    )

    if not docs_passed:
        logger.warning(
            "gate2_failed",
            reason="insufficient_docs",
            relevant_count=relevant_count,
            query=query[:100],
        )
        return Gate2Result(
            passed=False,
            reason=Gate2FailureReason.INSUFFICIENT_DOCS,
            message=docs_msg,
            max_similarity=max_sim,
            relevant_count=relevant_count,
            domain_ratio=0.0,
            details={
                "min_required": config.min_relevant_docs,
                "found": relevant_count,
                "min_score": config.min_doc_score,
            },
        )

    # Step 3: Domain validation (OAR-39)
    domain_passed, domain_ratio, domain_msg = check_domain_validation(
        documents, config=config
    )

    if not domain_passed:
        logger.warning(
            "gate2_failed",
            reason="domain_mismatch",
            domain_ratio=domain_ratio,
            query=query[:100],
        )
        return Gate2Result(
            passed=False,
            reason=Gate2FailureReason.DOMAIN_MISMATCH,
            message=domain_msg,
            max_similarity=max_sim,
            relevant_count=relevant_count,
            domain_ratio=domain_ratio,
            details={
                "threshold": config.domain_ratio_threshold,
                "actual_ratio": domain_ratio,
            },
        )

    # All checks passed
    logger.info(
        "gate2_passed",
        max_similarity=max_sim,
        relevant_count=relevant_count,
        domain_ratio=domain_ratio,
        query=query[:100],
    )

    return Gate2Result(
        passed=True,
        reason=None,
        message="검색 결과 검증 통과",
        max_similarity=max_sim,
        relevant_count=relevant_count,
        domain_ratio=domain_ratio,
        details={
            "similarity_threshold": config.similarity_threshold,
            "min_docs_required": config.min_relevant_docs,
            "domain_threshold": config.domain_ratio_threshold,
        },
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def validate_retrieval(
    query: str,
    documents: list[dict],
    similarity_threshold: float = 0.7,
    min_docs: int = 3,
    min_doc_score: float = 0.6,
    domain_ratio: float = 0.8,
) -> Gate2Result:
    """
    Validate retrieval with custom thresholds.

    Convenience function for one-off validation with non-default settings.

    Args:
        query: User's query
        documents: Retrieved documents
        similarity_threshold: Max score threshold
        min_docs: Minimum relevant document count
        min_doc_score: Score threshold for "relevant"
        domain_ratio: Required oncology document ratio

    Returns:
        Gate2Result
    """
    config = Gate2Config(
        similarity_threshold=similarity_threshold,
        min_relevant_docs=min_docs,
        min_doc_score=min_doc_score,
        domain_ratio_threshold=domain_ratio,
    )
    return check_retrieval_confidence(query, documents, config)


def is_retrieval_confident(query: str, documents: list[dict]) -> bool:
    """
    Simple boolean check for retrieval confidence.

    Args:
        query: User's query
        documents: Retrieved documents

    Returns:
        True if all Gate 2 checks pass
    """
    result = check_retrieval_confidence(query, documents)
    return result.passed


# ============================================================================
# DEMO
# ============================================================================

if __name__ == "__main__":
    print("=== Gate 2: Retrieval Confidence Demo ===\n")

    # Sample documents (simulating retrieval results)
    good_docs = [
        {
            "id": "doc1",
            "text": "EGFR mutations are found in 15% of lung cancer patients. Targeted therapy with erlotinib shows 70% response rates.",
            "score": 0.89,
            "metadata": {"title": "EGFR in NSCLC"}
        },
        {
            "id": "doc2",
            "text": "Immunotherapy has transformed treatment of metastatic melanoma. Checkpoint inhibitors show durable responses.",
            "score": 0.82,
            "metadata": {"title": "Immunotherapy Advances"}
        },
        {
            "id": "doc3",
            "text": "The FLAURA trial demonstrated osimertinib superiority in EGFR-mutant NSCLC with improved overall survival.",
            "score": 0.78,
            "metadata": {"title": "FLAURA Trial Results"}
        },
        {
            "id": "doc4",
            "text": "Chemotherapy remains a backbone of cancer treatment, often combined with targeted agents.",
            "score": 0.65,
            "metadata": {"title": "Chemotherapy Combinations"}
        },
    ]

    bad_docs_low_similarity = [
        {"id": "doc1", "text": "Some medical text...", "score": 0.45},
        {"id": "doc2", "text": "Other text...", "score": 0.38},
    ]

    off_topic_docs = [
        {"id": "doc1", "text": "Heart disease prevention strategies...", "score": 0.85},
        {"id": "doc2", "text": "Cardiovascular health guidelines...", "score": 0.78},
        {"id": "doc3", "text": "Blood pressure management...", "score": 0.72},
    ]

    # Test 1: Good documents
    print("Test 1: Good oncology documents")
    print("-" * 40)
    result = check_retrieval_confidence("EGFR inhibitors in lung cancer", good_docs)
    print(f"Passed: {result.passed}")
    print(f"Max similarity: {result.max_similarity:.2f}")
    print(f"Relevant docs: {result.relevant_count}")
    print(f"Domain ratio: {result.domain_ratio:.0%}")
    print(f"Message: {result.message}")
    print()

    # Test 2: Low similarity
    print("Test 2: Low similarity documents")
    print("-" * 40)
    result = check_retrieval_confidence("xyz123 random query", bad_docs_low_similarity)
    print(f"Passed: {result.passed}")
    print(f"Reason: {result.reason}")
    print(f"Max similarity: {result.max_similarity:.2f}")
    print(f"Message: {result.message}")
    print()

    # Test 3: Off-topic documents
    print("Test 3: Off-topic (cardiology) documents")
    print("-" * 40)
    result = check_retrieval_confidence("heart disease", off_topic_docs)
    print(f"Passed: {result.passed}")
    print(f"Reason: {result.reason}")
    print(f"Domain ratio: {result.domain_ratio:.0%}")
    print(f"Message: {result.message}")
    print()

    # Test 4: Empty documents
    print("Test 4: Empty documents")
    print("-" * 40)
    result = check_retrieval_confidence("any query", [])
    print(f"Passed: {result.passed}")
    print(f"Reason: {result.reason}")
    print(f"Message: {result.message}")
    print()

    # Show individual check functions
    print("=== Individual Check Functions ===\n")

    print("check_similarity_threshold():")
    passed, score, msg = check_similarity_threshold(good_docs)
    print(f"  Passed: {passed}, Max Score: {score:.2f}")
    print()

    print("check_min_relevant_docs():")
    passed, count, msg = check_min_relevant_docs(good_docs)
    print(f"  Passed: {passed}, Count: {count}")
    print()

    print("check_domain_validation():")
    passed, ratio, msg = check_domain_validation(good_docs)
    print(f"  Passed: {passed}, Ratio: {ratio:.0%}")
