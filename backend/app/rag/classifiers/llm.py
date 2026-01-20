"""LLM API 기반 도메인 분류기

GPT-4o-mini를 사용하여 쿼리가 Oncology 도메인인지 분류합니다.
Zero-shot 모델보다 한국어 및 복합 쿼리에 대해 더 정확한 분류가 가능합니다.

스펙:
- 모델: gpt-4o-mini (기본) 또는 다른 OpenAI 모델
- 분류 클래스: oncology, cardiology, neurology, general_medicine, non_medical
- 프롬프트 기반 분류로 맥락 이해 가능
- 한국어/영어 모두 지원

사용법:
    from app.rag import get_classifier
    classifier = get_classifier("llm_gpt4o_mini_v1")
    result = classifier.classify("면역요법의 부작용은 무엇인가요?")
"""

import json
import logging
import os
import time
from typing import Any

from app.rag.base import ClassificationResult
from app.rag.registry import register_classifier

logger = logging.getLogger(__name__)

# 분류 프롬프트 템플릿
CLASSIFICATION_SYSTEM_PROMPT = """You are a medical domain classifier. Your task is to classify user queries into one of the following categories:

Categories:
1. **oncology** - Cancer, tumors, chemotherapy, immunotherapy, radiation therapy, targeted therapy, carcinoma, lymphoma, leukemia, melanoma, sarcoma, cancer treatments, cancer biomarkers (EGFR, KRAS, HER2, PD-L1, etc.), cancer staging, metastasis
2. **cardiology** - Heart diseases, cardiovascular conditions, arrhythmia, hypertension, coronary artery disease, heart failure, cardiac procedures
3. **neurology** - Brain disorders, nervous system diseases, stroke, epilepsy, Alzheimer's, Parkinson's, multiple sclerosis, neuropathy
4. **general_medicine** - General healthcare, common diseases, symptoms, treatments that don't fit specific specialties above
5. **non_medical** - Questions unrelated to medicine (weather, sports, food, entertainment, technology, etc.)

Important notes:
- Immunotherapy (면역요법, pembrolizumab, nivolumab, etc.) is primarily an ONCOLOGY treatment
- Chemotherapy side effects are ONCOLOGY topics
- Cancer-related questions should ALWAYS be classified as oncology
- If a query mentions cancer, tumor, or cancer treatments, classify as oncology
- Classify based on the PRIMARY intent of the query

Respond with ONLY a JSON object in this exact format:
{"category": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}"""

CLASSIFICATION_USER_PROMPT = """Classify this query:
"{query}"

Respond with ONLY the JSON object."""


@register_classifier
class LLMDomainClassifier:
    """LLM API 기반 Oncology 도메인 분류기

    OpenAI GPT-4o-mini를 사용하여 쿼리의 도메인을 분류합니다.
    한국어와 복합적인 의료 질문에 대해 더 정확한 분류가 가능합니다.

    장점:
    - 한국어 쿼리에 대한 높은 이해도
    - 맥락 기반 분류 (immunotherapy = oncology 등)
    - 프롬프트로 분류 규칙 명시 가능

    단점:
    - API 호출 비용 발생
    - 네트워크 의존성
    - 응답 시간 ~200-500ms

    사용법:
        from app.rag import get_classifier
        classifier = get_classifier("llm_gpt4o_mini_v1")
        result = classifier.classify("EGFR 변이 폐암 치료")
    """

    name = "llm_gpt4o_mini_v1"

    # 허용되는 도메인
    ALLOWED_DOMAINS = ["oncology"]

    # 유효한 카테고리 목록
    VALID_CATEGORIES = ["oncology", "cardiology", "neurology", "general_medicine", "non_medical"]

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        threshold: float = 0.3,
        temperature: float = 0.0,
        timeout: float = 10.0,
    ):
        """분류기 초기화

        Args:
            model: OpenAI 모델 이름 (기본: gpt-4o-mini)
            threshold: 허용 도메인 판정 임계값 (기본 0.3)
            temperature: LLM temperature (0.0 권장 - 일관성)
            timeout: API 타임아웃 (초)
        """
        self.model = model
        self.threshold = threshold
        self.temperature = temperature
        self.timeout = timeout

        self._client = None
        self._enabled = os.getenv("DOMAIN_CLASSIFIER_ENABLED", "true").lower() == "true"
        self._mode = os.getenv("DOMAIN_CLASSIFIER_MODE", "warn")  # warn | block

    def _get_client(self):
        """OpenAI 클라이언트 (Lazy Loading)"""
        if self._client is None:
            from openai import OpenAI
            from app.config import settings

            api_key = settings.openai_api_key
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is not set. "
                    "Please set it in .env file or environment variable."
                )

            # settings에서 API 키를 가져와서 명시적으로 전달
            self._client = OpenAI(api_key=api_key)
        return self._client

    def classify(self, query: str, **kwargs: Any) -> ClassificationResult:
        """쿼리 도메인 분류

        Args:
            query: 분류할 쿼리 텍스트

        Returns:
            ClassificationResult: 분류 결과
        """
        # 비활성화 시 항상 허용
        if not self._enabled:
            return ClassificationResult(
                category="oncology",
                confidence=1.0,
                is_allowed=True,
                reason="Domain classifier disabled",
            )

        # 빈 쿼리 처리
        if not query or not query.strip():
            return ClassificationResult(
                category="unknown",
                confidence=0.0,
                is_allowed=True,
                reason="Empty query",
            )

        start_time = time.perf_counter()

        try:
            client = self._get_client()

            # LLM 호출
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": CLASSIFICATION_USER_PROMPT.format(query=query)},
                ],
                temperature=self.temperature,
                max_tokens=150,
                timeout=self.timeout,
            )

            elapsed = time.perf_counter() - start_time
            raw_content = response.choices[0].message.content.strip()

            # JSON 파싱
            try:
                result = json.loads(raw_content)
                category = result.get("category", "unknown")
                confidence = float(result.get("confidence", 0.5))
                reasoning = result.get("reasoning", "")

                # 유효성 검증
                if category not in self.VALID_CATEGORIES:
                    logger.warning(f"[LLMClassifier] Invalid category: {category}, defaulting to unknown")
                    category = "unknown"
                    confidence = 0.5

            except json.JSONDecodeError as e:
                logger.error(f"[LLMClassifier] JSON parse error: {e}, raw: {raw_content}")
                category = "unknown"
                confidence = 0.5
                reasoning = f"Parse error: {raw_content}"

            # 허용 여부 판단
            is_allowed = category in self.ALLOWED_DOMAINS and confidence >= self.threshold

            # 경고 모드에서는 항상 허용하되 로그 남김
            if self._mode == "warn" and not is_allowed:
                logger.warning(
                    f"[LLMClassifier] Off-domain query: "
                    f"category={category}, confidence={confidence:.2%}, "
                    f"reasoning={reasoning}, "
                    f"latency={elapsed*1000:.0f}ms, "
                    f"query={query[:100]}..."
                )
                is_allowed = True  # 경고 모드에서는 진행 허용

            reason = None
            if not is_allowed:
                reason = (
                    f"Query classified as '{category}' with {confidence:.0%} confidence. "
                    f"This system specializes in oncology (cancer research). "
                    f"Reasoning: {reasoning}"
                )

            logger.info(
                f"[LLMClassifier] Classified: category={category}, "
                f"confidence={confidence:.2%}, latency={elapsed*1000:.0f}ms"
            )

            return ClassificationResult(
                category=category,
                confidence=confidence,
                is_allowed=is_allowed,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"[LLMClassifier] Classification failed: {e}")
            # 오류 시 허용 (fail-open)
            return ClassificationResult(
                category="error",
                confidence=0.0,
                is_allowed=True,
                reason=f"Classification error: {str(e)}",
            )

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model": self.model,
            "threshold": self.threshold,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "enabled": self._enabled,
            "mode": self._mode,
            "allowed_domains": self.ALLOWED_DOMAINS,
            "valid_categories": self.VALID_CATEGORIES,
        }
