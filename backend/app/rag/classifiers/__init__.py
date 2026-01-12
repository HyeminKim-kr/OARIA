"""도메인 분류기 모듈

Zero-shot Classification 및 LLM API를 사용한 쿼리 도메인 분류기를 제공합니다.
Gate 1에서 Off-domain 쿼리를 감지하는 데 사용됩니다.

사용 가능한 분류기:
1. pubmedbert_domain_v1 - Zero-shot Classification (BART-MNLI)
2. llm_gpt4o_mini_v1 - LLM API 기반 (GPT-4o-mini, 권장)

사용법:
    from app.rag import get_classifier

    # Zero-shot 분류기
    classifier = get_classifier("pubmedbert_domain_v1")
    result = classifier.classify("EGFR mutation treatment")

    # LLM 분류기 (한국어에 더 정확)
    classifier = get_classifier("llm_gpt4o_mini_v1")
    result = classifier.classify("면역요법의 부작용은 무엇인가요?")

    if not result.is_allowed:
        print(f"Off-domain: {result.category} ({result.confidence:.0%})")

경고 메시지:
    from app.rag.classifiers.messages import get_warning_message, format_warning_response
    message = get_warning_message("cardiology", language="ko")
"""

from .base import ClassifierProtocol
from .pubmedbert import PubMedBERTDomainClassifier
from .llm import LLMDomainClassifier
from .messages import (
    get_warning_message,
    get_example_questions,
    format_warning_response,
    get_full_warning_text,
)

__all__ = [
    "ClassifierProtocol",
    # Classifiers
    "PubMedBERTDomainClassifier",
    "LLMDomainClassifier",
    # Messages
    "get_warning_message",
    "get_example_questions",
    "format_warning_response",
    "get_full_warning_text",
]
