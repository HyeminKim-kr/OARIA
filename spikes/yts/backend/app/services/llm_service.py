"""LLM 서비스

OpenAI GPT 모델을 사용한 응답 생성
스트리밍 지원
"""

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import settings
from app.schemas.chat import Reference


SYSTEM_PROMPT = """당신은 암 연구 분야의 전문 AI 어시스턴트입니다.
사용자의 질문에 대해 제공된 연구 논문 컨텍스트를 기반으로 정확하고 도움이 되는 답변을 제공합니다.

규칙:
1. 제공된 컨텍스트에 기반하여 답변하세요
2. 각 주장에 대해 [1], [2] 등의 형식으로 출처를 인용하세요
3. 컨텍스트에 없는 정보는 명시적으로 "제공된 자료에는 없지만..."이라고 표시하세요
4. 전문적이지만 이해하기 쉽게 설명하세요
5. 한국어로 답변하세요

컨텍스트:
{context}
"""


@dataclass
class LLMResponse:
    """LLM 응답"""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int


@dataclass
class StreamChunk:
    """스트리밍 청크"""

    token: str
    is_done: bool = False
    usage: dict[str, int] | None = None


class LLMService:
    """LLM 응답 생성 서비스"""

    _instance: "LLMService | None" = None
    _client: OpenAI | None = None

    def __new__(cls) -> "LLMService":
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> OpenAI | None:
        """OpenAI 클라이언트 반환"""
        if self._client is None and settings.openai_api_key:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    @property
    def use_mock(self) -> bool:
        """Mock 모드 여부"""
        return not settings.openai_api_key

    def generate(
        self,
        question: str,
        context: str,
        references: list[Reference],
    ) -> LLMResponse:
        """동기 응답 생성 (전체 응답)

        Args:
            question: 사용자 질문
            context: RAG 검색 결과 컨텍스트
            references: 참조 목록

        Returns:
            LLM 응답
        """
        import time

        start = time.perf_counter()

        if self.use_mock:
            content = self._mock_response(question, references)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return LLMResponse(
                content=content,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=elapsed_ms,
            )

        client = self._get_client()
        system_prompt = SYSTEM_PROMPT.format(context=context)

        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
            latency_ms=elapsed_ms,
        )

    def generate_stream(
        self,
        question: str,
        context: str,
        references: list[Reference],
    ) -> Generator[StreamChunk, None, None]:
        """스트리밍 응답 생성

        Args:
            question: 사용자 질문
            context: RAG 검색 결과 컨텍스트
            references: 참조 목록

        Yields:
            스트리밍 청크
        """
        if self.use_mock:
            yield from self._mock_stream(question, references)
            return

        client = self._get_client()
        system_prompt = SYSTEM_PROMPT.format(context=context)

        stream = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.7,
            max_tokens=2000,
            stream=True,
            stream_options={"include_usage": True},
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield StreamChunk(token=chunk.choices[0].delta.content)

            # 마지막 청크에 usage 정보 포함
            if chunk.usage:
                yield StreamChunk(
                    token="",
                    is_done=True,
                    usage={
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    },
                )

    def _mock_response(
        self,
        question: str,
        references: list[Reference],
    ) -> str:
        """Mock 응답 생성"""
        ref_texts = []
        for i, ref in enumerate(references, 1):
            ref_texts.append(f"[{i}] {ref.title} ({ref.journal}, {ref.year})")

        refs_str = "\n".join(ref_texts) if ref_texts else "참조 없음"

        return f"""**질문**: {question}

이 질문에 대해 제공된 연구 논문을 기반으로 답변드리겠습니다.

(Mock 응답 - OpenAI API 키가 설정되지 않았습니다)

**참조 문헌**:
{refs_str}
"""

    def _mock_stream(
        self,
        question: str,
        references: list[Reference],
    ) -> Generator[StreamChunk, None, None]:
        """Mock 스트리밍 응답"""
        import time

        content = self._mock_response(question, references)

        # 단어 단위로 스트리밍
        words = content.split(" ")
        for i, word in enumerate(words):
            yield StreamChunk(token=word + " " if i < len(words) - 1 else word)
            time.sleep(0.02)  # 스트리밍 효과

        yield StreamChunk(
            token="",
            is_done=True,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )


# 싱글톤 인스턴스
llm_service = LLMService()


def get_llm_service() -> LLMService:
    """LLM 서비스 의존성"""
    return llm_service
