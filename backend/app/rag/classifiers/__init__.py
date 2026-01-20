"""도메인 분류기 모듈

Zero-shot Classification 및 LLM API를 사용한 쿼리 도메인 분류기를 제공합니다.
Gate 1에서 Off-domain 쿼리를 감지하는 데 사용됩니다.

사용 가능한 분류기:
1. pubmedbert_domain_v1 - Zero-shot Classification (BART-MNLI)
2. llm_gpt4o_mini_v1 - LLM API 기반 (GPT-4o-mini, 권장)
3. bc5cdr_ner_v1 - BC5CDR NER (Chemical, Disease)
4. multiner_v1 - MultiNER (Disease, Chemical, Gene)

사용법:
    from app.rag import get_classifier

    # Zero-shot 분류기 (영어)
    classifier = get_classifier("pubmedbert_domain_v1")
    result = classifier.classify("EGFR mutation treatment")

    # 다국어 Zero-shot 분류기 (한국어/영어)
    classifier = get_classifier("multilingual_v1")
    result = classifier.classify("EGFR 변이 폐암 치료")

    # LLM 분류기 (가장 정확, API 비용 발생)
    classifier = get_classifier("llm_gpt4o_mini_v1")
    result = classifier.classify("면역요법의 부작용은 무엇인가요?")

    if not result.is_allowed:
        print(f"Off-domain: {result.category} ({result.confidence:.0%})")

    # NER 분류기 (엔티티 추출)
    ner = get_classifier("bc5cdr_ner_v1")
    entities = ner.extract("Cisplatin treats lung cancer.")
    for e in entities.entities:
        print(f"{e.text}: {e.label} ({e.score:.2%})")

경고 메시지:
    from app.rag.classifiers.messages import get_warning_message, format_warning_response
    message = get_warning_message("cardiology", language="ko")
"""

from .base import ClassifierProtocol
from .pubmedbert import PubMedBERTDomainClassifier
from .multilingual import MultilingualDomainClassifier
from .llm import LLMDomainClassifier
from .bc5cdr_ner import BC5CDRNERClassifier
from .multiner import MultiNERClassifier
from .messages import (
    get_warning_message,
    get_example_questions,
    format_warning_response,
    get_full_warning_text,
)

__all__ = [
    "ClassifierProtocol",
    # Domain Classifiers
    "PubMedBERTDomainClassifier",
    "MultilingualDomainClassifier",
    "LLMDomainClassifier",
    # NER Classifiers
    "BC5CDRNERClassifier",
    "MultiNERClassifier",
    # Messages
    "get_warning_message",
    "get_example_questions",
    "format_warning_response",
    "get_full_warning_text",
]

