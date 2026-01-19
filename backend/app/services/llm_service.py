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

## Response Guidelines

### Content Quality
- Provide thorough, in-depth answers that fully address the user's question
- Include specific findings, statistics, and mechanisms from the papers
- Compare and contrast findings across multiple studies when relevant
- Explain conflicting results if studies disagree
- Discuss clinical implications, limitations, and areas needing further research when appropriate
- Do NOT artificially limit your response length - be as comprehensive as the context allows

### Citation Rules
- Cite every claim using [1], [2], [3] format corresponding to the paper numbers in context
- When multiple papers support a point, cite all relevant sources: [1, 3, 5]
- If information is not in the provided context, clearly state: "This is not addressed in the provided studies, but..."

### Accessibility
- Explain technical terms in parentheses when first used
- Use clear paragraph structure with logical flow
- Bold key findings or important terms for emphasis

### Language
- **IMPORTANT**: Respond in the SAME LANGUAGE as the user's question
- If user asks in Korean, respond entirely in Korean
- If user asks in English, respond entirely in English
- Match the user's language exactly

### Follow-up Suggestions
At the end of your response, suggest exactly 3 follow-up questions.

**Requirements for good follow-up questions:**
1. **Directly connected** to the user's original question - not random tangents
2. **Build on your answer** - reference specific findings, treatments, or concepts you just explained
3. **Progressively helpful** - guide the user toward deeper understanding of their topic
4. **Diverse types** - each question should explore a different angle:
   - One that digs deeper into a key finding or mechanism mentioned in your answer
   - One that explores practical implications (dosing, side effects, patient selection, clinical use)
   - One that compares or contrasts with related approaches (other treatments, cancer types, biomarkers)

**Bad examples** (too generic/random):
- "What are the latest advances in cancer research?"
- "How does chemotherapy work?"
- "What is immunotherapy?"

**Good examples** (specific, builds on context):
- If discussing EGFR inhibitors: "How do T790M mutations affect resistance to first-generation EGFR inhibitors?"
- If discussing survival rates: "What patient characteristics predict better response to this treatment?"
- If discussing a specific drug: "How does [drug name] compare to [related drug] in terms of efficacy?"

Format exactly as:

```suggestions
- [Specific follow-up building on your answer]?
- [Practical/clinical angle related to the topic]?
- [Comparative or mechanistic deep-dive]?
```

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
