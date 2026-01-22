"""Tavily Service - Tier 3 Web Search

Tavily API를 사용한 웹 검색
https://tavily.com/

주요 기능:
- 연구/학술 컨텍스트 웹 검색
- 검색 깊이 조절 (basic/advanced)
- 결과 자동 요약
"""

import logging
import hashlib
import httpx
from dataclasses import dataclass
from typing import Literal, Optional

from app.config import settings
from .types import EvidenceSnippetV3, SearchTier, ClaimType

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


@dataclass
class TavilySearchResult:
    """Tavily 검색 결과 아이템"""

    title: str
    url: str
    content: str  # 페이지 내용 요약
    raw_content: str | None  # 원본 내용 (advanced 모드)
    score: float  # 관련성 점수 (0-1)
    published_date: str | None

    def to_evidence_snippet(
        self,
        claim_type: ClaimType = ClaimType.MECHANISM,
    ) -> EvidenceSnippetV3:
        """EvidenceSnippetV3로 변환"""
        snippet_id = hashlib.md5(
            f"tavily:{self.url[:100]}".encode()
        ).hexdigest()[:12]

        # content 또는 raw_content 사용
        text = self.raw_content or self.content
        if len(text) > 3000:
            text = text[:3000] + "..."

        return EvidenceSnippetV3(
            snippet_id=f"web_{snippet_id}",
            text=text,
            source_tier=SearchTier.WEB,
            source_tool="tavily",
            claim_type=claim_type,
            url=self.url,
            title=self.title,
            relevance_score=self.score,
        )


class TavilyService:
    """Tavily API 서비스

    Study Plan Agent v3 Tier 3 검색용
    월 1,000회 무료 한도 (search_web_monthly_limit)
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._api_key: str = settings.tavily_api_key

    @property
    def is_available(self) -> bool:
        """API 키가 설정되어 있는지 확인"""
        return bool(self._api_key)

    async def _ensure_client(self):
        """HTTP 클라이언트 지연 초기화"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)

    async def search(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        max_results: int = 5,
        include_raw_content: bool = False,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[TavilySearchResult]:
        """Tavily 웹 검색

        Args:
            query: 검색 쿼리
            search_depth: 검색 깊이 ("basic" 또는 "advanced")
                - basic: 빠른 검색, 요약만 제공
                - advanced: 깊은 검색, 원본 내용 포함 (2배 비용)
            max_results: 최대 결과 수 (1-10)
            include_raw_content: advanced 모드에서 원본 내용 포함
            include_domains: 포함할 도메인 목록
            exclude_domains: 제외할 도메인 목록

        Returns:
            검색 결과 목록
        """
        if not self.is_available:
            logger.warning("tavily_api_key_not_set")
            return []

        await self._ensure_client()

        # 연구 관련 도메인 기본 포함
        if include_domains is None:
            include_domains = []

        # 학술 검색에 부적합한 도메인 기본 제외
        if exclude_domains is None:
            exclude_domains = [
                "reddit.com",
                "quora.com",
                "twitter.com",
                "facebook.com",
            ]

        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": min(max_results, 10),
            "include_answer": False,  # 요약 응답 불필요
            "include_raw_content": include_raw_content and search_depth == "advanced",
            "include_domains": include_domains if include_domains else None,
            "exclude_domains": exclude_domains,
        }

        # None 값 제거
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            response = await self._client.post(
                TAVILY_API_URL,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    TavilySearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        raw_content=item.get("raw_content"),
                        score=item.get("score", 0.5),
                        published_date=item.get("published_date"),
                    )
                )

            logger.info(
                "tavily_search query=%s depth=%s results=%d",
                query[:50],
                search_depth,
                len(results),
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "tavily_search_http_error status=%d body=%s",
                e.response.status_code,
                e.response.text[:200],
            )
            return []
        except Exception as e:
            logger.error("tavily_search_error error=%s", str(e))
            return []

    async def search_for_evidence(
        self,
        query: str,
        claim_type: ClaimType = ClaimType.MECHANISM,
        search_depth: Literal["basic", "advanced"] = "basic",
        max_results: int = 5,
        academic_focus: bool = True,
    ) -> list[EvidenceSnippetV3]:
        """Evidence 수집용 웹 검색

        Args:
            query: 검색 쿼리
            claim_type: Evidence 유형
            search_depth: 검색 깊이
            max_results: 최대 결과 수
            academic_focus: 학술 도메인 우선

        Returns:
            EvidenceSnippetV3 목록
        """
        include_domains = None
        if academic_focus:
            # 학술/의학 신뢰 도메인 우선
            include_domains = [
                "nih.gov",
                "ncbi.nlm.nih.gov",
                "pubmed.gov",
                "nature.com",
                "sciencedirect.com",
                "springer.com",
                "wiley.com",
                "cell.com",
                "pnas.org",
                "jci.org",
                "nejm.org",
                "jamanetwork.com",
                "thelancet.com",
                "bmj.com",
                "frontiersin.org",
                "mdpi.com",
                "biorxiv.org",
                "medrxiv.org",
            ]

        results = await self.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_raw_content=search_depth == "advanced",
            include_domains=include_domains,
        )

        return [r.to_evidence_snippet(claim_type=claim_type) for r in results]

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 싱글톤 인스턴스
tavily_service = TavilyService()
