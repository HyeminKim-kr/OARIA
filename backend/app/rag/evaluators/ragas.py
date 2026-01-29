"""RAGAS 기반 품질 평가기

LLM을 사용하여 Faithfulness와 Answer Relevancy를 측정합니다.
RAGAS 라이브러리 대신 OpenAI API를 직접 사용하여 구현합니다.
"""

import json
import logging
import time

from openai import AsyncOpenAI

from app.config import settings
from app.rag.base import EvaluationResult
from app.rag.registry import register_evaluator

logger = logging.getLogger(__name__)


# Faithfulness 평가 프롬프트
FAITHFULNESS_PROMPT = """You are an expert evaluator assessing the faithfulness of an answer.

Faithfulness measures whether the answer is grounded in the provided context.
Every claim in the answer should be supported by information in the context.

## Evaluation Criteria
- Score 1.0: All claims are fully supported by the context
- Score 0.8: Most claims are supported, minor extrapolations
- Score 0.6: Some claims are supported, some unsupported
- Score 0.4: Few claims are supported, significant hallucination
- Score 0.2: Mostly hallucinated content
- Score 0.0: No grounding in context

## Input

Question: {question}

Context:
{context}

Answer:
{answer}

## Task

Evaluate the faithfulness of the answer to the context.

Respond with JSON only:
{{
    "score": <float between 0 and 1>,
    "reasoning": "<brief explanation>"
}}"""


# Answer Relevancy 평가 프롬프트
RELEVANCY_PROMPT = """You are an expert evaluator assessing the relevancy of an answer.

Answer Relevancy measures whether the answer directly addresses the question asked.
The answer should be on-topic, complete, and helpful.

## Evaluation Criteria
- Score 1.0: Perfectly addresses the question, comprehensive
- Score 0.8: Addresses the question well, minor gaps
- Score 0.6: Partially addresses the question
- Score 0.4: Tangentially related, misses key points
- Score 0.2: Barely related to the question
- Score 0.0: Completely off-topic

## Input

Question: {question}

Answer:
{answer}

## Task

Evaluate how well the answer addresses the question.

Respond with JSON only:
{{
    "score": <float between 0 and 1>,
    "reasoning": "<brief explanation>"
}}"""


@register_evaluator
class RAGASEvaluator:
    """RAGAS 메트릭 기반 답변 품질 평가

    LLM을 사용하여 Faithfulness와 Answer Relevancy를 측정합니다.

    메트릭:
    - Faithfulness: 답변이 컨텍스트에 충실한 정도 (0.0 ~ 1.0)
    - Answer Relevancy: 답변이 질문에 관련된 정도 (0.0 ~ 1.0)

    환경 변수:
    - GATE3_ENABLED: true/false - Gate 3 활성화 여부
    """

    name = "ragas_v1"

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI | None:
        """AsyncOpenAI 클라이언트 반환"""
        if self._client is None and settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> EvaluationResult:
        """품질 평가 수행

        Args:
            question: 사용자 질문
            answer: 생성된 답변
            contexts: RAG 검색 결과 컨텍스트들

        Returns:
            EvaluationResult: 평가 결과
        """
        start_time = time.perf_counter()

        client = self._get_client()
        if not client:
            logger.warning("OpenAI client not available, returning default scores")
            return EvaluationResult(
                faithfulness=None,
                answer_relevancy=None,
                passed=True,
                details={"error": "OpenAI client not configured"},
            )

        # 컨텍스트 결합
        combined_context = "\n\n---\n\n".join(contexts) if contexts else ""

        # 병렬로 두 메트릭 평가
        try:
            faithfulness_score, faithfulness_reason = await self._evaluate_faithfulness(
                client, question, answer, combined_context
            )
            relevancy_score, relevancy_reason = await self._evaluate_relevancy(
                client, question, answer
            )
        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")
            return EvaluationResult(
                faithfulness=None,
                answer_relevancy=None,
                passed=True,
                details={"error": str(e)},
            )

        # 전체 점수 계산 (평균)
        overall_score = None
        if faithfulness_score is not None and relevancy_score is not None:
            overall_score = (faithfulness_score + relevancy_score) / 2

        # 통과 여부 판정
        passed = True
        if faithfulness_score is not None and faithfulness_score < 0.85:
            passed = False
        if relevancy_score is not None and relevancy_score < 0.80:
            passed = False

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"RAGAS evaluation completed: faithfulness={faithfulness_score}, "
            f"relevancy={relevancy_score}, passed={passed}, latency={latency_ms}ms"
        )

        return EvaluationResult(
            faithfulness=faithfulness_score,
            answer_relevancy=relevancy_score,
            overall_score=overall_score,
            passed=passed,
            details={
                "faithfulness_reasoning": faithfulness_reason,
                "relevancy_reasoning": relevancy_reason,
                "latency_ms": latency_ms,
            },
        )

    async def _evaluate_faithfulness(
        self,
        client: AsyncOpenAI,
        question: str,
        answer: str,
        context: str,
    ) -> tuple[float | None, str | None]:
        """Faithfulness 평가"""
        prompt = FAITHFULNESS_PROMPT.format(
            question=question,
            context=context,
            answer=answer,
        )

        try:
            response = await client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
            )

            content = response.choices[0].message.content or ""

            # JSON 파싱
            # JSON 블록이 있으면 추출
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            score = float(result.get("score", 0))
            reasoning = result.get("reasoning", "")

            return score, reasoning

        except Exception as e:
            logger.error(f"Faithfulness evaluation failed: {e}")
            return None, str(e)

    async def _evaluate_relevancy(
        self,
        client: AsyncOpenAI,
        question: str,
        answer: str,
    ) -> tuple[float | None, str | None]:
        """Answer Relevancy 평가"""
        prompt = RELEVANCY_PROMPT.format(
            question=question,
            answer=answer,
        )

        try:
            response = await client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
            )

            content = response.choices[0].message.content or ""

            # JSON 파싱
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            score = float(result.get("score", 0))
            reasoning = result.get("reasoning", "")

            return score, reasoning

        except Exception as e:
            logger.error(f"Relevancy evaluation failed: {e}")
            return None, str(e)

    def get_config(self) -> dict:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "metrics": ["faithfulness", "answer_relevancy"],
            "thresholds": {
                "faithfulness": 0.85,
                "answer_relevancy": 0.80,
            },
            "model": settings.openai_chat_model,
        }
