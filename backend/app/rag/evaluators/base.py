"""Evaluator Protocol 정의"""

from typing import Protocol

from app.rag.base import EvaluationResult


class EvaluatorProtocol(Protocol):
    """품질 평가 전략 인터페이스

    모든 evaluator는 이 인터페이스를 구현해야 합니다.
    """

    name: str  # 레지스트리 등록 이름

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
        ...

    def get_config(self) -> dict:
        """현재 설정 반환"""
        ...
