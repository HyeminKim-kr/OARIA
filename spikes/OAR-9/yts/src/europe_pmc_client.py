"""
Europe PMC API 클라이언트

동기/비동기 버전 모두 지원
기반: OAR-19/yts/src/europe_pmc_client.py
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Callable

import httpx


@dataclass
class PaperInfo:
    """검색 결과 기본 정보"""
    pmid: str | None
    pmcid: str | None
    doi: str | None
    title: str
    journal: str | None
    year: int | None
    is_open_access: bool
    has_full_text: bool


class EuropePMCClient:
    """Europe PMC REST API 클라이언트 - 동기 버전"""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, delay: float = 0.3, timeout: float = 60.0):
        self.client = httpx.Client(timeout=timeout)
        self.delay = delay
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def search(
        self,
        query: str,
        limit: int = 10,
        open_access_only: bool = True,
    ) -> list[PaperInfo]:
        """논문 검색"""
        if open_access_only:
            query = f"{query} AND OPEN_ACCESS:Y"

        params = {
            "query": query,
            "format": "json",
            "pageSize": min(limit, 1000),
            "resultType": "core",
        }

        self._rate_limit()
        response = self.client.get(f"{self.BASE_URL}/search", params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("resultList", {}).get("result", [])

        return self._parse_results(results)

    def get_fulltext_xml(self, pmcid: str) -> Optional[str]:
        """PMC ID로 전문 XML 반환"""
        if not pmcid:
            return None

        pmcid = pmcid.replace("PMC", "")
        url = f"{self.BASE_URL}/PMC{pmcid}/fullTextXML"

        try:
            self._rate_limit()
            response = self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError:
            return None

    def _parse_results(self, results: list[dict]) -> list[PaperInfo]:
        papers = []
        for item in results:
            try:
                year = item.get("pubYear")
                year = int(year) if year else None
            except ValueError:
                year = None

            papers.append(PaperInfo(
                pmid=item.get("pmid") or None,
                pmcid=item.get("pmcid") or None,
                doi=item.get("doi") or None,
                title=item.get("title", ""),
                journal=item.get("journalTitle"),
                year=year,
                is_open_access=item.get("isOpenAccess", "N") == "Y",
                has_full_text=(
                    item.get("inEPMC", "N") == "Y" or
                    item.get("inPMC", "N") == "Y" or
                    bool(item.get("pmcid"))
                ),
            ))
        return papers

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AsyncEuropePMCClient:
    """Europe PMC REST API 클라이언트 - 비동기 버전"""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(
        self,
        max_concurrent: int = 10,
        delay: float = 0.1,
        timeout: float = 60.0
    ):
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def search(
        self,
        query: str,
        limit: int = 10,
        open_access_only: bool = True,
    ) -> list[PaperInfo]:
        """논문 검색"""
        if open_access_only:
            query = f"{query} AND OPEN_ACCESS:Y"

        params = {
            "query": query,
            "format": "json",
            "pageSize": min(limit, 1000),
            "resultType": "core",
        }

        response = await self._client.get(f"{self.BASE_URL}/search", params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("resultList", {}).get("result", [])

        return self._parse_results(results)

    async def get_fulltext_xml(self, pmcid: str) -> Optional[str]:
        """PMC ID로 전문 XML 반환 (세마포어로 동시성 제한)"""
        if not pmcid:
            return None

        pmcid = pmcid.replace("PMC", "")
        url = f"{self.BASE_URL}/PMC{pmcid}/fullTextXML"

        async with self._semaphore:
            try:
                await asyncio.sleep(self.delay)
                response = await self._client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError:
                return None

    async def get_fulltext_xml_batch(
        self,
        pmcids: list[str],
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> dict[str, Optional[str]]:
        """여러 논문 XML 병렬 수집"""
        results = {}
        total = len(pmcids)
        completed = 0

        async def fetch_one(pmcid: str):
            nonlocal completed
            xml = await self.get_fulltext_xml(pmcid)
            results[pmcid] = xml
            completed += 1
            if on_progress:
                on_progress(completed, total, pmcid)
            return pmcid, xml

        await asyncio.gather(*[fetch_one(pmcid) for pmcid in pmcids])
        return results

    def _parse_results(self, results: list[dict]) -> list[PaperInfo]:
        papers = []
        for item in results:
            try:
                year = item.get("pubYear")
                year = int(year) if year else None
            except ValueError:
                year = None

            papers.append(PaperInfo(
                pmid=item.get("pmid") or None,
                pmcid=item.get("pmcid") or None,
                doi=item.get("doi") or None,
                title=item.get("title", ""),
                journal=item.get("journalTitle"),
                year=year,
                is_open_access=item.get("isOpenAccess", "N") == "Y",
                has_full_text=(
                    item.get("inEPMC", "N") == "Y" or
                    item.get("inPMC", "N") == "Y" or
                    bool(item.get("pmcid"))
                ),
            ))
        return papers
