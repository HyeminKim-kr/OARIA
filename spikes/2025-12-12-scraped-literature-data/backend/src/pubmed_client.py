"""
OARIA Literature - PubMed E-utilities 클라이언트

NCBI E-utilities API를 사용하여 PubMed 논문을 검색하고 수집합니다.

API 엔드포인트:
- ESearch: 키워드 → PMID 리스트
- ESummary: PMID → 메타데이터
- EFetch: PMID → Abstract/Full-text

Rate Limit:
- 무료: 3 requests/second
- API Key: 10 requests/second
"""

import asyncio
import time
from typing import Optional
from xml.etree import ElementTree as ET

import httpx

from .config import settings


class RateLimiter:
    """Rate Limiter - 초당 요청 수 제한"""
    
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
    """PubMed E-utilities 클라이언트"""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ncbi_api_key
        rate = 10.0 if self.api_key else settings.pubmed_rate_limit
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
    
    async def _request(self, method: str, url: str, params: dict, max_retries: int = 3) -> httpx.Response:
        """Exponential backoff로 재시도하는 HTTP 요청"""
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
        """검색어에 해당하는 총 논문 수 조회"""
        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "term": term,
            "retmax": 0,
            "usehistory": "n",
        }
        
        if date_from:
            params["datetype"] = "pdat"
            params["mindate"] = date_from.replace("-", "/")
            params["maxdate"] = (date_to or "3000").replace("-", "/")
        
        url = f"{self.BASE_URL}/esearch.fcgi"
        response = await self._request("GET", url, params)
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
        """검색어로 PMID 리스트 조회"""
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
            params["datetype"] = "pdat"
            params["mindate"] = date_from.replace("-", "/")
            params["maxdate"] = (date_to or "3000").replace("-", "/")
        
        url = f"{self.BASE_URL}/esearch.fcgi"
        response = await self._request("GET", url, params)
        data = response.json()
        
        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        total = int(result.get("count", 0))
        
        return pmids, total
    
    async def fetch_summaries(self, pmids: list[str]) -> dict:
        """PMID 리스트로 메타데이터 조회"""
        if not pmids:
            return {}
        
        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
        }
        
        url = f"{self.BASE_URL}/esummary.fcgi"
        response = await self._request("GET", url, params)
        data = response.json()
        
        results = {}
        result_data = data.get("result", {})
        
        for pmid in pmids:
            if pmid not in result_data:
                continue
                
            doc = result_data[pmid]
            authors = [a.get("name", "") for a in doc.get("authors", []) if a.get("name")]
            
            results[pmid] = {
                "title": doc.get("title", ""),
                "authors": authors,
                "journal": doc.get("source", ""),
                "pubdate": doc.get("pubdate", "") or doc.get("epubdate", ""),
                "doi": doc.get("elocationid", "").replace("doi: ", ""),
            }
        
        return results
    
    async def fetch_abstracts(self, pmids: list[str]) -> dict[str, str]:
        """PMID 리스트로 Abstract 조회"""
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
        response = await self._request("GET", url, params)
        
        results = {}
        try:
            root = ET.fromstring(response.content)
            
            for article in root.findall(".//PubmedArticle"):
                pmid_elem = article.find(".//PMID")
                if pmid_elem is None:
                    continue
                pmid = pmid_elem.text
                
                abstract_parts = []
                for abstract_text in article.findall(".//AbstractText"):
                    label = abstract_text.get("Label", "")
                    text = "".join(abstract_text.itertext()).strip()
                    
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
                
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
    ) -> tuple[list[dict], int]:
        """검색부터 Abstract 수집까지 한번에 수행"""
        # 1. PMID 검색
        pmids, total = await self.search_pmids(term, offset, limit, date_from, date_to)
        
        if not pmids:
            return [], total
        
        # 2. 메타데이터 조회
        summaries = await self.fetch_summaries(pmids)
        
        # 3. Abstract 조회
        abstracts = await self.fetch_abstracts(pmids)
        
        # 4. 결합
        papers = []
        for pmid in pmids:
            meta = summaries.get(pmid, {})
            abstract = abstracts.get(pmid, "")
            
            papers.append({
                "pmid": pmid,
                "title": meta.get("title", ""),
                "abstract": abstract,
                "authors": meta.get("authors", []),
                "journal": meta.get("journal", ""),
                "pubdate": meta.get("pubdate", ""),
                "doi": meta.get("doi", ""),
            })
        
        return papers, total


# 싱글톤 인스턴스
_client_instance: Optional[PubMedClient] = None


async def get_pubmed_client() -> PubMedClient:
    """싱글톤 클라이언트 인스턴스 반환"""
    global _client_instance
    if _client_instance is None:
        _client_instance = PubMedClient()
        await _client_instance.__aenter__()
    return _client_instance
