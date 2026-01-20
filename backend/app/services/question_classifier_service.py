"""질문 유형 분류 서비스

논문 채팅에서 사용자 질문을 분류하여 적절한 RAG 전략을 적용합니다.

질문 유형:
- summary: 요약/핵심 질문 → Reranker 없이 빠른 응답
- qa: 구체적 QA → Retrieval + Reranker
- evidence: 근거 요청 → Retrieval + Reranker + offset 강조
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class QuestionType(str, Enum):
    """질문 유형"""
    SUMMARY = "summary"      # 요약/핵심 질문
    QA = "qa"                # 구체적 QA
    EVIDENCE = "evidence"    # 근거 요청


@dataclass
class RAGStrategy:
    """RAG 전략 설정"""
    use_reranker: bool
    top_k: int
    sections: list[str] | None
    min_rerank_score: float | None


# 질문 유형별 RAG 전략
RAG_STRATEGIES: dict[QuestionType, RAGStrategy] = {
    QuestionType.SUMMARY: RAGStrategy(
        use_reranker=False,
        top_k=3,
        sections=["abstract", "introduction", "conclusion"],
        min_rerank_score=None,
    ),
    QuestionType.QA: RAGStrategy(
        use_reranker=True,
        top_k=5,
        sections=None,  # 모든 섹션
        min_rerank_score=0.5,
    ),
    QuestionType.EVIDENCE: RAGStrategy(
        use_reranker=True,
        top_k=7,
        sections=["methods", "results", "discussion"],
        min_rerank_score=0.6,
    ),
}


CLASSIFICATION_PROMPT = """사용자의 질문을 분류하세요.

분류 유형:
- summary: 논문의 핵심, 요약, 결론, 주요 내용, "뭐야", "무엇" 등을 묻는 질문
- qa: 구체적인 내용, 메커니즘, 수치, 방법론, 비교, 효과에 대한 질문
- evidence: 근거 위치, 출처, "어디에 있어", "어느 부분", "어디서" 등의 질문

질문: {question}

반드시 아래 JSON 형식으로만 답하세요:
{{"type": "summary 또는 qa 또는 evidence", "confidence": 0.0에서 1.0 사이 숫자}}"""


class QuestionClassifier:
    """LLM 기반 질문 유형 분류기"""

    _instance: "QuestionClassifier | None" = None
    _client: AsyncOpenAI | None = None

    def __new__(cls) -> "QuestionClassifier":
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> AsyncOpenAI | None:
        """AsyncOpenAI 클라이언트 반환"""
        if self._client is None and settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def classify(self, query: str) -> tuple[QuestionType, float]:
        """질문 유형 분류

        Args:
            query: 사용자 질문

        Returns:
            (질문 유형, 신뢰도)
        """
        client = self._get_client()
        if not client:
            logger.warning("[QuestionClassifier] OpenAI API 키 없음, 기본값(QA) 반환")
            return QuestionType.QA, 0.5

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": CLASSIFICATION_PROMPT.format(question=query),
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=50,
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            q_type_str = result.get("type", "qa")
            confidence = float(result.get("confidence", 0.7))

            # 유효한 타입인지 확인
            try:
                q_type = QuestionType(q_type_str)
            except ValueError:
                logger.warning(f"[QuestionClassifier] 알 수 없는 타입: {q_type_str}, QA로 처리")
                q_type = QuestionType.QA

            logger.info(f"[QuestionClassifier] '{query[:30]}...' → {q_type.value} (confidence={confidence:.2f})")
            return q_type, confidence

        except Exception as e:
            logger.exception(f"[QuestionClassifier] 분류 실패: {e}")
            return QuestionType.QA, 0.5

    def get_strategy(self, question_type: QuestionType) -> RAGStrategy:
        """질문 유형에 맞는 RAG 전략 반환"""
        return RAG_STRATEGIES.get(question_type, RAG_STRATEGIES[QuestionType.QA])


# 싱글톤 인스턴스
question_classifier = QuestionClassifier()


def get_question_classifier() -> QuestionClassifier:
    """QuestionClassifier 의존성"""
    return question_classifier
