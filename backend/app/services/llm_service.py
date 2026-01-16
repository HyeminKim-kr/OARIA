"""LLM 서비스

OpenAI GPT 모델을 사용한 응답 생성
비동기 지원: AsyncOpenAI 사용 (2026-01-15)
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.chat import Reference


SYSTEM_PROMPT = """당신은 암 연구 분야의 전문 AI 어시스턴트입니다.
사용자의 질문에 대해 제공된 연구 논문 컨텍스트를 기반으로 정확하고 풍부한 답변을 제공합니다.

## 답변 구조 (반드시 따를 것)

### 1. 핵심 요약
- 질문에 대한 직접적인 답변을 2-3문장으로 명확하게 제시

### 2. 상세 분석
- 관련 연구 결과들의 주요 발견을 구체적으로 설명
- 여러 논문이 있다면 **공통점과 차이점**을 비교 분석
- 작용 메커니즘이나 원인이 있다면 상세히 설명
- 수치나 통계가 있다면 구체적으로 인용

### 3. 근거 논문 요약
- 인용한 각 논문의 핵심 기여를 간략히 정리
- 연구 설계(임상시험, 메타분석 등)와 대상자 정보가 있다면 포함

### 4. 임상적 의미 및 한계 (해당되는 경우)
- 연구 결과의 실제 적용 가능성
- 연구의 한계점이나 추가 연구가 필요한 부분

### 5. 추천 질문
- 사용자가 다음으로 궁금해할 만한 후속 질문 3개를 제안
- 반드시 아래 형식으로 작성:

```suggestions
- 첫 번째 추천 질문?
- 두 번째 추천 질문?
- 세 번째 추천 질문?
```

추천 질문 유형:
- **심화**: 현재 주제를 더 깊이 파고드는 질문
- **관련**: 연관된 다른 치료법, 메커니즘, 암종 등
- **실용**: 부작용, 임상 적용, 예후 등 실제적인 질문

## 작성 규칙

1. **출처 인용**: 모든 주장에 [1], [2] 형식으로 출처 표기
2. **논문 통합**: 여러 논문이 비슷한 결론이면 통합하여 설명하고, 상충되면 양측 모두 제시
3. **불확실성 표현**: 컨텍스트에 없는 정보는 "제공된 자료에서는 확인되지 않지만..." 명시
4. **전문성과 접근성**: 전문 용어는 필요시 괄호 안에 쉬운 설명 추가
5. **언어**: 한국어로 답변

## 컨텍스트 (검색된 연구 논문)

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
    """비동기 LLM 응답 생성 서비스"""

    _instance: "LLMService | None" = None
    _client: AsyncOpenAI | None = None

    def __new__(cls) -> "LLMService":
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> AsyncOpenAI | None:
        """AsyncOpenAI 클라이언트 반환"""
        if self._client is None and settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    @property
    def use_mock(self) -> bool:
        """Mock 모드 여부"""
        return not settings.openai_api_key

    async def generate(
        self,
        question: str,
        context: str,
        references: list[Reference],
    ) -> LLMResponse:
        """비동기 응답 생성 (전체 응답)

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

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,  # 과학/의료 도메인은 낮은 temperature로 일관된 답변
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

    async def generate_stream(
        self,
        question: str,
        context: str,
        references: list[Reference],
    ) -> AsyncGenerator[StreamChunk, None]:
        """비동기 스트리밍 응답 생성

        Args:
            question: 사용자 질문
            context: RAG 검색 결과 컨텍스트
            references: 참조 목록

        Yields:
            스트리밍 청크
        """
        if self.use_mock:
            async for chunk in self._mock_stream_async(question, references):
                yield chunk
            return

        client = self._get_client()
        system_prompt = SYSTEM_PROMPT.format(context=context)

        stream = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,  # 과학/의료 도메인은 낮은 temperature로 일관된 답변
            max_tokens=2000,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in stream:
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

    async def _mock_stream_async(
        self,
        question: str,
        references: list[Reference],
    ) -> AsyncGenerator[StreamChunk, None]:
        """비동기 Mock 스트리밍 응답"""
        content = self._mock_response(question, references)

        # 단어 단위로 스트리밍
        words = content.split(" ")
        for i, word in enumerate(words):
            yield StreamChunk(token=word + " " if i < len(words) - 1 else word)
            await asyncio.sleep(0.02)  # 스트리밍 효과

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
