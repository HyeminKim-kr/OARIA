"""
Europe PMC API 클라이언트

Raw XML을 반환하여 OAR-19 파싱 로직과 연계
OAR-18 참고하여 재구현
"""

import time
from dataclasses import dataclass
from typing import Optional

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
    """Europe PMC REST API 클라이언트 (Raw XML 반환)"""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, delay: float = 0.3, timeout: float = 60.0):
        self.client = httpx.Client(timeout=timeout)
        self.delay = delay
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Rate limit 준수"""
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
        """논문 검색 (메타데이터만)"""
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

    def get_fulltext_xml(self, pmcid: str) -> Optional[str]:
        """PMC ID로 전문 XML 원본 반환

        Args:
            pmcid: PMC ID (예: "PMC12345678" 또는 "12345678")

        Returns:
            원본 XML 문자열 (태그 제거 안함)
        """
        if not pmcid:
            return None

        pmcid = pmcid.replace("PMC", "")
        url = f"{self.BASE_URL}/PMC{pmcid}/fullTextXML"

        try:
            self._rate_limit()
            response = self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            print(f"전문 수집 실패 ({pmcid}): {e}")
            return None

    def close(self):
        """클라이언트 정리"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
