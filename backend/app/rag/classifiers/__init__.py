"""도메인 분류기 모듈

Zero-shot Classification을 사용한 쿼리 도메인 분류기를 제공합니다.
Gate 1에서 Off-domain 쿼리를 감지하는 데 사용됩니다.

사용법:
    from app.rag import get_classifier
    classifier = get_classifier("pubmedbert_domain_v1")
    result = classifier.classify("EGFR mutation treatment")

    if not result.is_allowed:
        print(f"Off-domain: {result.category} ({result.confidence:.0%})")

경고 메시지:
    from app.rag.classifiers.messages import get_warning_message, format_warning_response
    message = get_warning_message("cardiology", language="ko")
"""

from .base import ClassifierProtocol
from .pubmedbert import PubMedBERTDomainClassifier
from .messages import (
    get_warning_message,
    get_example_questions,
    format_warning_response,
    get_full_warning_text,
)

__all__ = [
    "ClassifierProtocol",
    "PubMedBERTDomainClassifier",
    # Messages
    "get_warning_message",
    "get_example_questions",
    "format_warning_response",
    "get_full_warning_text",
]
