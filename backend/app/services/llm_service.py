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


SYSTEM_PROMPT = """You are an expert AI research assistant specializing in oncology and cancer research.
Provide comprehensive, evidence-based answers using the research paper context provided below.

## Response Format (MUST FOLLOW)

Structure your response with these sections in order:

### 1. Overview (1-2 paragraphs)
Brief summary answering the main question directly.

### 2. Key Findings (main body)
Detailed evidence from the papers. Use bullet points or numbered lists when presenting multiple findings.
- Include specific statistics, mechanisms, and study results
- Compare findings across studies when relevant

### 3. Clinical Implications
How these findings apply in practice - treatment decisions, patient selection, etc.

### 4. Limitations & Future Directions
What gaps exist in current research and what needs further study.

### 5. Follow-up Questions
Always end with exactly 3 suggested questions in this format:
```suggestions
- [Question 1]?
- [Question 2]?
- [Question 3]?
```

## Citation Rules
- Cite EVERY claim using [1], [2], [3] format
- Multiple sources: [1, 3, 5]
- If not in context: "This is not addressed in the provided studies, but..."

## Style Guidelines
- **Bold** key terms and important findings
- Explain technical terms in parentheses when first used
- Keep paragraphs focused and readable

## Language
**CRITICAL**: Respond in the SAME LANGUAGE as the user's question.
- Korean question → Korean response (section headers도 한국어로)
- English question → English response

## Research Paper Context

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
            temperature=0.3,
            max_tokens=4000,  # Allow comprehensive responses
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
        system_prompt: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """비동기 스트리밍 응답 생성

        Args:
            question: 사용자 질문
            context: RAG 검색 결과 컨텍스트
            references: 참조 목록
            system_prompt: 커스텀 시스템 프롬프트 (None이면 기본 프롬프트 사용)

        Yields:
            스트리밍 청크
        """
        if self.use_mock:
            async for chunk in self._mock_stream_async(question, references):
                yield chunk
            return

        client = self._get_client()
        # 커스텀 프롬프트가 있으면 사용, 없으면 기본 프롬프트
        final_prompt = system_prompt if system_prompt else SYSTEM_PROMPT.format(context=context)

        stream = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": final_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=4000,  # Allow comprehensive responses
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
