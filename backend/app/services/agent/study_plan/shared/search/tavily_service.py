"""Tavily Web Search Service

Tavily API를 통한 웹 검색.
과학/의학 정보에 최적화.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


TAVILY_BASE_URL = "https://api.tavily.com"


@dataclass
class TavilyResult:
    """Tavily 검색 결과 항목"""
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str] = None


@dataclass
class TavilySearchResult:
    """Tavily 검색 결과"""
    results: list[TavilyResult]
    query: str
    answer: Optional[str] = None  # AI 요약 (있는 경우)


class TavilyService:
    """
    Tavily Web Search API 서비스
    
    - 과학/의학 관련 웹 검색
    - 실험 프로토콜, 시약 정보 등
    """
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.api_key = settings.tavily_api_key
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def is_available(self) -> bool:
        """API 키 설정 여부"""
        return bool(self.api_key)
    
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 lazy 초기화"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def search(
        self,
        query: str,
        search_depth: str = "basic",  # basic | advanced
        max_results: int = 5,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
    ) -> TavilySearchResult:
        """
        웹 검색
        
        Args:
            query: 검색 쿼리
            search_depth: 검색 깊이 (basic: 빠름, advanced: 정밀)
            max_results: 최대 결과 수
            include_domains: 포함할 도메인
            exclude_domains: 제외할 도메인
            
        Returns:
            TavilySearchResult
        """
        if not self.is_available:
            logger.warning("[Tavily] API key not configured")
            return TavilySearchResult(results=[], query=query)
        
        client = await self._get_client()
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True,
        }
        
        # 도메인 필터
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains
        
        # 과학/의학 검색에 유용한 도메인
        if not include_domains:
            payload["include_domains"] = [
                "pubmed.ncbi.nlm.nih.gov",
                "nature.com",
                "science.org",
                "cell.com",
                "protocols.io",
                "addgene.org",
                "thermofisher.com",
                "sigmaaldrich.com",
            ]
        
        try:
            response = await client.post(
                f"{TAVILY_BASE_URL}/search",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("results", []):
                result = TavilyResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=float(item.get("score", 0)),
                    published_date=item.get("published_date"),
                )
                results.append(result)
            
            logger.info(f"[Tavily] Search '{query[:50]}...' returned {len(results)} results")
            
            return TavilySearchResult(
                results=results,
                query=query,
                answer=data.get("answer"),
            )
            
        except Exception as e:
            logger.error(f"[Tavily] Search failed: {e}")
            return TavilySearchResult(results=[], query=query)
    
    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 싱글톤 인스턴스
tavily_service = TavilyService()
