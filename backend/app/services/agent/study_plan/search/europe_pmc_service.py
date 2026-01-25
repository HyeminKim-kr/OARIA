"""Europe PMC Service

Europe PMC API를 통한 논문 검색.
참조: backend/app/services/similar_papers_service.py
"""

import logging
from dataclasses import dataclass
from typing import Optional
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)


EPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@dataclass
class EPMCPaper:
    """Europe PMC 논문"""
    pmcid: str
    pmid: Optional[str]
    title: str
    abstract: str
    journal: str
    year: int
    authors: list[str]
    is_open_access: bool
    citations: int = 0


@dataclass
class EPMCSearchResult:
    """Europe PMC 검색 결과"""
    papers: list[EPMCPaper]
    total_count: int
    query: str


class EuropePmcService:
    """
    Europe PMC API 서비스
    
    - 논문 검색
    - Full-text XML 조회
    """
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 lazy 초기화"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def search(
        self,
        query: str,
        open_access_only: bool = True,
        year_from: Optional[int] = None,
        max_results: int = 20,
    ) -> EPMCSearchResult:
        """
        논문 검색
        
        Args:
            query: 검색 쿼리
            open_access_only: OA 논문만 검색
            year_from: 시작 연도
            max_results: 최대 결과 수
            
        Returns:
            EPMCSearchResult
        """
        client = await self._get_client()
        
        # 쿼리 구성
        full_query = query
        if open_access_only:
            full_query += " AND OPEN_ACCESS:y"
        if year_from:
            full_query += f" AND PUB_YEAR:[{year_from} TO *]"
        
        params = {
            "query": full_query,
            "format": "json",
            "pageSize": min(max_results, 100),
            "resultType": "core",
            "sort": "RELEVANCE desc",
        }
        
        try:
            response = await client.get(f"{EPMC_BASE_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            papers = []
            result_list = data.get("resultList", {}).get("result", [])
            
            for item in result_list:
                paper = EPMCPaper(
                    pmcid=item.get("pmcid", ""),
                    pmid=item.get("pmid"),
                    title=item.get("title", ""),
                    abstract=item.get("abstractText", ""),
                    journal=item.get("journalTitle", ""),
                    year=int(item.get("pubYear", 0)),
                    authors=[
                        a.get("fullName", "") 
                        for a in item.get("authorList", {}).get("author", [])
                    ],
                    is_open_access=item.get("isOpenAccess") == "Y",
                    citations=int(item.get("citedByCount", 0)),
                )
                papers.append(paper)
            
            total = int(data.get("hitCount", len(papers)))
            
            logger.info(f"[EPMC] Search '{query[:50]}...' returned {len(papers)} papers (total: {total})")
            
            return EPMCSearchResult(
                papers=papers,
                total_count=total,
                query=query,
            )
            
        except Exception as e:
            logger.error(f"[EPMC] Search failed: {e}")
            return EPMCSearchResult(papers=[], total_count=0, query=query)
    
    async def get_fulltext_xml(
        self,
        pmc_id: str,
        sections: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """
        Full-text XML 조회
        
        Args:
            pmc_id: PMC ID (예: PMC1234567)
            sections: 추출할 섹션 (None이면 전체)
            
        Returns:
            섹션별 텍스트 딕셔너리
        """
        client = await self._get_client()
        
        # PMC 형식 정규화
        if not pmc_id.startswith("PMC"):
            pmc_id = f"PMC{pmc_id}"
        
        url = f"{EPMC_BASE_URL}/{pmc_id}/fullTextXML"
        
        try:
            response = await client.get(url)
            response.raise_for_status()
            
            root = ElementTree.fromstring(response.content)
            
            result = {}
            
            # Methods 섹션
            if sections is None or "methods" in sections:
                methods = self._extract_section(root, ["methods", "materials and methods", "experimental"])
                if methods:
                    result["methods"] = methods
            
            # Results 섹션
            if sections is None or "results" in sections:
                results = self._extract_section(root, ["results"])
                if results:
                    result["results"] = results
            
            # Discussion 섹션
            if sections is None or "discussion" in sections:
                discussion = self._extract_section(root, ["discussion"])
                if discussion:
                    result["discussion"] = discussion
            
            logger.info(f"[EPMC] Extracted {len(result)} sections from {pmc_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"[EPMC] Fulltext fetch failed for {pmc_id}: {e}")
            return {}
    
    def _extract_section(self, root: ElementTree.Element, keywords: list[str]) -> str:
        """XML에서 특정 섹션 추출"""
        for sec in root.iter("sec"):
            title_elem = sec.find("title")
            if title_elem is not None and title_elem.text:
                title_lower = title_elem.text.lower()
                if any(kw in title_lower for kw in keywords):
                    return " ".join(sec.itertext())
        return ""
    
    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 싱글톤 인스턴스
europe_pmc_service = EuropePmcService()
