"""논문 요약 생성 서비스

논문의 전문 또는 특정 섹션을 요약합니다.
LLM을 사용하여 구조화된 요약을 생성합니다.

지원 요약 유형:
- full: 논문 전체 요약
- abstract: 초록 기반 요약
- methods: 연구 방법론 요약
- results: 연구 결과 요약
- conclusion: 결론 및 시사점 요약
"""

import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI

from app.config import settings
from app.services.weaviate_service import weaviate_service

if TYPE_CHECKING:
    from app.models.paper import Paper


SummaryType = Literal["full", "abstract", "methods", "results", "conclusion"]


SUMMARY_PROMPTS = {
    "full": """당신은 의학 논문 요약 전문가입니다.
아래 논문의 핵심 내용을 체계적으로 요약해주세요.

## 요약 구조
1. **연구 목적**: 왜 이 연구가 수행되었는지
2. **연구 방법**: 어떻게 연구가 진행되었는지 (대상자, 방법론)
3. **주요 결과**: 핵심 발견 사항 (수치 포함)
4. **결론 및 의의**: 연구의 결론과 임상적/과학적 의미

## 작성 규칙
- 한국어로 작성
- 각 항목은 2-3문장으로 간결하게
- 중요한 수치나 통계는 반드시 포함
- 전문 용어는 필요시 괄호 안에 설명 추가

## 논문 내용
{content}""",

    "abstract": """당신은 의학 논문 전문가입니다.
아래 논문의 초록을 바탕으로 핵심 내용을 요약해주세요.

## 요약 형식
- 연구 배경과 목적을 1-2문장으로
- 핵심 결과를 2-3문장으로
- 결론을 1문장으로

## 작성 규칙
- 한국어로 작성
- 총 4-6문장 이내
- 핵심 수치 포함

## 초록 내용
{content}""",

    "methods": """당신은 의학 연구 방법론 전문가입니다.
아래 논문의 연구 방법을 요약해주세요.

## 요약 항목
1. **연구 설계**: 임상시험, 코호트, 메타분석 등
2. **연구 대상**: 포함/제외 기준, 대상자 수
3. **주요 측정 지표**: 일차/이차 평가변수
4. **통계 분석**: 사용된 통계 방법

## 작성 규칙
- 한국어로 작성
- 각 항목 1-2문장
- 구체적인 수치 포함

## 방법론 내용
{content}""",

    "results": """당신은 의학 연구 결과 분석 전문가입니다.
아래 논문의 연구 결과를 요약해주세요.

## 요약 항목
1. **일차 평가변수 결과**: 핵심 지표의 변화/비교
2. **이차 평가변수 결과**: 부가적인 발견
3. **부분군 분석**: 특정 그룹별 차이 (있는 경우)
4. **안전성 결과**: 부작용, 이상반응 (있는 경우)

## 작성 규칙
- 한국어로 작성
- 모든 주요 수치(%, HR, OR, p-value 등) 포함
- 통계적 유의성 명시

## 결과 내용
{content}""",

    "conclusion": """당신은 의학 연구 해석 전문가입니다.
아래 논문의 결론과 시사점을 요약해주세요.

## 요약 항목
1. **주요 결론**: 연구의 핵심 결론
2. **임상적 의의**: 실제 진료에의 적용 가능성
3. **연구 한계**: 저자가 언급한 제한점
4. **향후 연구 방향**: 추가 연구 필요성

## 작성 규칙
- 한국어로 작성
- 각 항목 1-2문장
- 객관적 서술

## 결론 내용
{content}"""
}

SECTION_MAPPING = {
    "full": ["abstract", "introduction", "methods", "results", "discussion", "conclusion"],
    "abstract": ["abstract"],
    "methods": ["methods", "materials_and_methods", "materials and methods", "study design"],
    "results": ["results", "findings"],
    "conclusion": ["discussion", "conclusion", "conclusions"],
}


@dataclass
class SummaryResult:
    """요약 결과"""

    summary_type: str
    summary: str
    sections_used: list[str]
    tokens_used: int
    latency_ms: int


class SummaryService:
    """논문 요약 생성 서비스"""

    _instance: "SummaryService | None" = None
    _client: AsyncOpenAI | None = None

    def __new__(cls) -> "SummaryService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> AsyncOpenAI | None:
        if self._client is None:
            api_key = settings.openai_api_key
            if api_key:
                self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def generate_summary(
        self,
        paper: "Paper",
        summary_type: SummaryType = "full",
        max_tokens: int = 1000,
        collection_name: str | None = None,
    ) -> SummaryResult:
        """논문 요약 생성

        Args:
            paper: Paper 모델 인스턴스
            summary_type: 요약 유형 (full, abstract, methods, results, conclusion)
            max_tokens: 최대 응답 토큰 수
            collection_name: Weaviate 컬렉션 이름

        Returns:
            SummaryResult
        """
        start = time.perf_counter()

        # 1. 필요한 섹션 내용 가져오기
        content, sections_used = self._get_paper_content(
            paper.paper_id, summary_type, collection_name
        )

        if not content:
            return SummaryResult(
                summary_type=summary_type,
                summary="요약할 내용을 찾을 수 없습니다.",
                sections_used=[],
                tokens_used=0,
                latency_ms=0,
            )

        # 2. LLM으로 요약 생성
        prompt = SUMMARY_PROMPTS.get(summary_type, SUMMARY_PROMPTS["full"])
        prompt = prompt.format(content=content)

        client = self._get_client()
        if not client:
            return SummaryResult(
                summary_type=summary_type,
                summary="LLM 서비스가 설정되지 않았습니다.",
                sections_used=sections_used,
                tokens_used=0,
                latency_ms=0,
            )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 의학 논문 요약 전문가입니다."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )

        summary = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        latency_ms = int((time.perf_counter() - start) * 1000)

        return SummaryResult(
            summary_type=summary_type,
            summary=summary,
            sections_used=sections_used,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

    async def generate_summary_stream(
        self,
        paper: "Paper",
        summary_type: SummaryType = "full",
        max_tokens: int = 1000,
        collection_name: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """논문 요약 스트리밍 생성

        Args:
            paper: Paper 모델 인스턴스
            summary_type: 요약 유형
            max_tokens: 최대 응답 토큰 수
            collection_name: Weaviate 컬렉션 이름

        Yields:
            요약 텍스트 청크
        """
        # 1. 필요한 섹션 내용 가져오기
        content, _ = self._get_paper_content(
            paper.paper_id, summary_type, collection_name
        )

        if not content:
            yield "요약할 내용을 찾을 수 없습니다."
            return

        # 2. LLM 스트리밍
        prompt = SUMMARY_PROMPTS.get(summary_type, SUMMARY_PROMPTS["full"])
        prompt = prompt.format(content=content)

        client = self._get_client()
        if not client:
            yield "LLM 서비스가 설정되지 않았습니다."
            return

        stream = await client.chat.completions.create(
            model=settings.openai_chat_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 의학 논문 요약 전문가입니다."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _get_paper_content(
        self,
        paper_id: str,
        summary_type: SummaryType,
        collection_name: str | None = None,
    ) -> tuple[str, list[str]]:
        """논문 섹션 내용 가져오기

        Args:
            paper_id: 논문 ID
            summary_type: 요약 유형
            collection_name: Weaviate 컬렉션 이름

        Returns:
            (섹션 내용, 사용된 섹션 목록)
        """
        target_sections = SECTION_MAPPING.get(summary_type, SECTION_MAPPING["full"])

        # Weaviate에서 해당 논문의 모든 청크 가져오기
        all_chunks = weaviate_service.get_by_paper_id(
            paper_id=paper_id,
            collection_name=collection_name,
        )

        if not all_chunks:
            return "", []

        # 섹션별로 그룹화
        section_contents: dict[str, list[dict]] = {}
        for chunk in all_chunks:
            section = chunk.get("section", "").lower()
            if section not in section_contents:
                section_contents[section] = []
            section_contents[section].append(chunk)

        # 대상 섹션 내용 추출
        content_parts = []
        sections_used = []

        for target_section in target_sections:
            target_lower = target_section.lower()
            for section_name, chunks in section_contents.items():
                if target_lower in section_name or section_name in target_lower:
                    # 청크 정렬 및 합치기
                    chunks.sort(key=lambda x: x.get("chunkIndex", 0))
                    section_text = " ".join(c.get("content", "") for c in chunks)
                    if section_text.strip():
                        content_parts.append(f"## {section_name.title()}\n{section_text}")
                        sections_used.append(section_name)

        content = "\n\n".join(content_parts)

        # 토큰 제한 (약 8000 토큰 = 32000자)
        if len(content) > 32000:
            content = content[:32000] + "...(내용 일부 생략)"

        return content, sections_used


# 싱글톤 인스턴스
summary_service = SummaryService()


def get_summary_service() -> SummaryService:
    """SummaryService 의존성"""
    return summary_service
