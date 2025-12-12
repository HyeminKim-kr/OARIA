"""
PubMed E-utilities 클라이언트

NCBI E-utilities API를 사용하여 PubMed 논문을 검색하고 수집합니다.

API 엔드포인트:
- ESearch: 키워드 → PMID 리스트
- ESummary: PMID → 메타데이터
- EFetch: PMID → Abstract/Full-text

Rate Limit:
- 무료: 3 requests/second
- API Key: 10 requests/second

설계 원칙:
1. 비동기 HTTP 요청 (httpx.AsyncClient)
2. 자동 rate limiting (초당 3회)
3. Exponential backoff 재시도
4. 배치 처리 최적화 (retmax=500)
"""

import asyncio
import time
import re
from typing import Optional
from xml.etree import ElementTree as ET

import httpx

from models import Paper, PaperMetadata


class RateLimiter:
    """
    Rate Limiter - 초당 요청 수 제한
    
    NCBI 무료 API는 초당 3회로 제한됩니다.
    이를 초과하면 IP가 일시 차단될 수 있습니다.
    """
    
    def __init__(self, requests_per_second: float = 3.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """요청 전 호출하여 rate limit 준수"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.monotonic()


class PubMedClient:
    """
    PubMed E-utilities 클라이언트
    
    사용 예시:
    ```python
    async with PubMedClient() as client:
        count = await client.get_count("breast cancer")
        papers = await client.search_and_fetch("breast cancer", limit=100)
    ```
    """
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: NCBI API Key (선택). 있으면 10 req/sec, 없으면 3 req/sec
        """
        self.api_key = api_key
        rate = 10.0 if api_key else 3.0
        self.rate_limiter = RateLimiter(rate)
        self._client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    def _get_base_params(self) -> dict:
        """기본 API 파라미터"""
        params = {"retmode": "json"}
        if self.api_key:
            params["api_key"] = self.api_key
        return params
    
    async def _request_with_retry(
        self, 
        method: str, 
        url: str, 
        params: dict,
        max_retries: int = 3
    ) -> httpx.Response:
        """
        Exponential backoff로 재시도하는 HTTP 요청
        
        실패 시 1초, 2초, 4초 간격으로 재시도합니다.
        이는 NCBI 서버의 일시적 오류를 안정적으로 처리합니다.
        """
        for attempt in range(max_retries):
            await self.rate_limiter.acquire()
            try:
                response = await self._client.request(method, url, params=params)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                print(f"[Retry {attempt + 1}/{max_retries}] Waiting {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
    
    async def get_count(
        self, 
        term: str, 
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> int:
        """
        검색어에 해당하는 총 논문 수 조회
        
        Args:
            term: 검색 키워드
            date_from: 시작일 (YYYY/MM/DD 또는 YYYY-MM-DD)
            date_to: 종료일
            
        Returns:
            총 논문 수
        """
        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "term": term,
            "retmax": 0,  # We only need count
            "usehistory": "n",
        }
        
        if date_from:
            date_from = date_from.replace("-", "/")
        if date_to:
            date_to = date_to.replace("-", "/")
            
        if date_from and date_to:
            params["datetype"] = "pdat"
            params["mindate"] = date_from
            params["maxdate"] = date_to
        elif date_from:
            params["datetype"] = "pdat"
            params["mindate"] = date_from
            params["maxdate"] = "3000"
        
        url = f"{self.BASE_URL}/esearch.fcgi"
        response = await self._request_with_retry("GET", url, params)
        data = response.json()
        
        return int(data.get("esearchresult", {}).get("count", 0))
    
    async def search_pmids(
        self,
        term: str,
        offset: int = 0,
        limit: int = 500,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> tuple[list[str], int]:
        """
        검색어로 PMID 리스트 조회
        
        Args:
            term: 검색 키워드
            offset: 시작 위치
            limit: 가져올 개수 (최대 10000)
            
        Returns:
            (PMID 리스트, 총 건수)
        """
        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "term": term,
            "retstart": offset,
            "retmax": min(limit, 10000),
            "sort": "relevance",
            "usehistory": "n",
        }
        
        if date_from:
            date_from = date_from.replace("-", "/")
        if date_to:
            date_to = date_to.replace("-", "/")
            
        if date_from and date_to:
            params["datetype"] = "pdat"
            params["mindate"] = date_from
            params["maxdate"] = date_to
        elif date_from:
            params["datetype"] = "pdat"
            params["mindate"] = date_from
            params["maxdate"] = "3000"
        
        url = f"{self.BASE_URL}/esearch.fcgi"
        response = await self._request_with_retry("GET", url, params)
        data = response.json()
        
        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        total = int(result.get("count", 0))
        
        return pmids, total
    
    async def fetch_summaries(self, pmids: list[str]) -> dict[str, PaperMetadata]:
        """
        PMID 리스트로 메타데이터 조회 (ESummary)
        
        Args:
            pmids: PMID 리스트
            
        Returns:
            {pmid: PaperMetadata} 딕셔너리
        """
        if not pmids:
            return {}
        
        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
        }
        
        url = f"{self.BASE_URL}/esummary.fcgi"
        response = await self._request_with_retry("GET", url, params)
        data = response.json()
        
        results = {}
        result_data = data.get("result", {})
        
        for pmid in pmids:
            if pmid not in result_data:
                continue
                
            doc = result_data[pmid]
            
            # 저자 추출
            authors = []
            for author in doc.get("authors", []):
                name = author.get("name", "")
                if name:
                    authors.append(name)
            
            # 출판일 추출
            pubdate = doc.get("pubdate", "")
            if not pubdate:
                pubdate = doc.get("epubdate", "")
            
            results[pmid] = PaperMetadata(
                title=doc.get("title", ""),
                authors=authors,
                journal=doc.get("source", ""),
                pubdate=pubdate,
                doi=doc.get("elocationid", "").replace("doi: ", ""),
            )
        
        return results
    
    async def fetch_abstracts(self, pmids: list[str]) -> dict[str, str]:
        """
        PMID 리스트로 Abstract 조회 (EFetch XML)
        
        Args:
            pmids: PMID 리스트
            
        Returns:
            {pmid: abstract_text} 딕셔너리
        """
        if not pmids:
            return {}
        
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
            "retmode": "xml",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{self.BASE_URL}/efetch.fcgi"
        response = await self._request_with_retry("GET", url, params)
        
        results = {}
        try:
            root = ET.fromstring(response.content)
            
            for article in root.findall(".//PubmedArticle"):
                # PMID 추출
                pmid_elem = article.find(".//PMID")
                if pmid_elem is None:
                    continue
                pmid = pmid_elem.text
                
                # Abstract 추출
                abstract_parts = []
                for abstract_text in article.findall(".//AbstractText"):
                    # Label이 있는 경우 (BACKGROUND:, METHODS: 등)
                    label = abstract_text.get("Label", "")
                    text = "".join(abstract_text.itertext()).strip()
                    
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
                
                # MeSH Terms 추출 (나중에 사용)
                results[pmid] = " ".join(abstract_parts)
                
        except ET.ParseError as e:
            print(f"[Error] XML 파싱 실패: {e}")
        
        return results
    
    async def search_and_fetch(
        self,
        term: str,
        offset: int = 0,
        limit: int = 20,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> tuple[list[Paper], int]:
        """
        검색부터 Abstract 수집까지 한번에 수행
        
        이 메서드는 다음 단계를 순차적으로 실행합니다:
        1. ESearch: 키워드 → PMID 리스트
        2. ESummary: PMID → 메타데이터 (제목, 저자, 저널)
        3. EFetch: PMID → Abstract 텍스트
        
        Args:
            term: 검색 키워드
            offset: 시작 위치
            limit: 가져올 논문 수
            
        Returns:
            (Paper 리스트, 총 건수)
        """
        # 1. PMID 검색
        pmids, total = await self.search_pmids(term, offset, limit, date_from, date_to)
        
        if not pmids:
            return [], total
        
        # 2. 메타데이터 조회
        summaries = await self.fetch_summaries(pmids)
        
        # 3. Abstract 조회
        abstracts = await self.fetch_abstracts(pmids)
        
        # 4. Paper 객체로 조합
        papers = []
        for pmid in pmids:
            metadata = summaries.get(pmid, PaperMetadata())
            abstract = abstracts.get(pmid, "")
            
            paper = Paper(
                pmid=pmid,
                metadata=metadata,
                abstract=abstract,
                status="ok" if abstract else "no_pmc",
                log=[f"Fetched at {time.strftime('%Y-%m-%d %H:%M:%S')}"]
            )
            papers.append(paper)
        
        return papers, total


# 단일 인스턴스 (모듈 레벨)
_client_instance: Optional[PubMedClient] = None


async def get_client() -> PubMedClient:
    """싱글톤 클라이언트 인스턴스 반환"""
    global _client_instance
    if _client_instance is None:
        _client_instance = PubMedClient()
        await _client_instance.__aenter__()
    return _client_instance
