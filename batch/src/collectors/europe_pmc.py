"""Europe PMC API 클라이언트

OAR-18 설계 기반:
- Search API: 논문 검색
- Fulltext API: XML 전문 수집
- Rate Limit 통합
"""

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator

import re

import httpx
import structlog

from ..config import settings
from ..models import Paper
from .rate_limiter import (
    CircuitOpenError,
    RateLimiter,
    RateLimiterConfig,
    RateLimitError,
    RetryableError,
)

logger = structlog.get_logger()


@dataclass
class CommentCorrection:
    """논문 관계 정보 (정정/철회/코멘트)"""

    id: str              # 관련 논문 PMID
    type: str            # 관계 타입 (Erratum for, Retraction of 등)
    source: str = ""     # 출처 (MED 등)
    reference: str = ""  # 참조 문자열


@dataclass
class CitationResult:
    """인용/참조 결과"""

    pmcid: str | None = None
    pmid: str | None = None
    doi: str | None = None
    title: str = ""
    source: str = ""  # MED, PMC, AGR 등


@dataclass
class CitationsPage:
    """인용 목록 페이지"""

    results: list[CitationResult]
    total_count: int
    has_more: bool = False


@dataclass
class SearchResult:
    """검색 결과"""

    pmcid: str
    pmid: str | None = None
    doi: str | None = None
    title: str = ""
    is_open_access: bool = True
    pub_types: list[str] = field(default_factory=list)
    comment_corrections: list[CommentCorrection] = field(default_factory=list)


@dataclass
class SearchPage:
    """검색 페이지 결과"""

    results: list[SearchResult]
    cursor: str | None  # 다음 페이지 커서
    total_count: int
    page_size: int


@dataclass
class EuropePMCClient:
    """Europe PMC API 클라이언트"""

    base_url: str = field(default_factory=lambda: settings.api.base_url)
    timeout: float = field(default_factory=lambda: settings.api.timeout)
    max_retries: int = field(default_factory=lambda: settings.api.max_retries)

    # 동시 요청 수 (search_query.max_concurrent 전달용)
    max_concurrent: int = field(default_factory=lambda: settings.api.max_concurrent)
    # RPS 제한 (None이면 max_concurrent * 2 사용 - 병렬 처리에 적합)
    rps_limit: float | None = None

    # Rate Limiter (post_init에서 생성)
    rate_limiter: RateLimiter | None = field(default=None, repr=False)

    def __post_init__(self):
        # rps_limit이 None이면 settings.api.rps_limit 사용 (기본 5.0)
        # Europe PMC는 높은 RPS에 대해 soft rate limiting을 적용할 수 있음
        # 안전하게 settings 기본값 또는 max_concurrent와 비슷한 수준으로 제한
        effective_rps = self.rps_limit or min(settings.api.rps_limit * 2, self.max_concurrent)

        self.rate_limiter = RateLimiter(
            RateLimiterConfig(
                rps_limit=effective_rps,
                max_concurrent=self.max_concurrent,
            )
        )

        logger.info(
            "europe_pmc_client_init",
            max_concurrent=self.max_concurrent,
            rps_limit=effective_rps,
            settings_rps_limit=settings.api.rps_limit,
        )

    # HTTP 클라이언트
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def __aenter__(self):
        # Connection pool 설정: 동시 요청 수에 맞게 충분한 연결 확보
        limits = httpx.Limits(
            max_connections=self.max_concurrent + 10,
            max_keepalive_connections=self.max_concurrent,
        )
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=limits,
            http2=False,  # HTTP/1.1 사용 (더 안정적)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Rate Limit이 적용된 HTTP 요청

        중요: response body를 rate limiter 내부에서 읽어야 함
        그렇지 않으면 동시 요청 시 connection이 닫힐 수 있음
        """
        for attempt in range(self.max_retries):
            try:
                await self.rate_limiter.acquire()

                try:
                    response = await self._client.request(method, url, **kwargs)

                    # 중요: body를 rate limiter release 전에 읽어야 함
                    # 동시 요청 시 connection pool 문제 방지
                    _ = await response.aread()

                    # 성공
                    if response.status_code < 400:
                        self.rate_limiter.record_success()
                        return response

                    # 429 Rate Limit
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = self.rate_limiter.record_429(
                            float(retry_after) if retry_after else None
                        )
                        raise RateLimitError(wait_time)

                    # 5xx 서버 에러
                    if response.status_code >= 500:
                        wait_time = self.rate_limiter.record_5xx()
                        raise RetryableError(response.status_code, wait_time)

                    # 4xx 클라이언트 에러 (재시도 불가)
                    response.raise_for_status()

                finally:
                    self.rate_limiter.release()

            except CircuitOpenError:
                logger.error("circuit_open", attempt=attempt)
                raise

            except (RateLimitError, RetryableError) as e:
                if attempt == self.max_retries - 1:
                    raise
                logger.warning(
                    "retrying", attempt=attempt, wait_time=e.wait_time, error=str(e)
                )
                await asyncio.sleep(e.wait_time)

            except httpx.TimeoutException:
                wait_time = self.rate_limiter.record_5xx()
                if attempt == self.max_retries - 1:
                    raise
                logger.warning("timeout_retry", attempt=attempt, wait_time=wait_time)
                await asyncio.sleep(wait_time)

        raise RuntimeError(f"Max retries ({self.max_retries}) exceeded")

    async def search(
        self,
        query: str,
        page_size: int = 1000,
        cursor: str | None = None,
    ) -> SearchPage:
        """논문 검색

        Args:
            query: 검색 쿼리 (예: "lung cancer immunotherapy")
            page_size: 페이지 크기 (최대 1000)
            cursor: 페이지네이션 커서

        Returns:
            SearchPage: 검색 결과 페이지
        """
        params = {
            "query": query,
            "resultType": "core",
            "pageSize": min(page_size, 1000),
            "format": "json",
        }

        if cursor:
            params["cursorMark"] = cursor

        url = f"{self.base_url}/search"
        response = await self._request("GET", url, params=params)
        data = response.json()

        results = []
        for item in data.get("resultList", {}).get("result", []):
            # PMC ID가 있는 것만 수집 (fulltext 가능)
            pmcid = item.get("pmcid")
            if not pmcid:
                continue

            # pubTypeList 추출
            pub_types = []
            pub_type_list = item.get("pubTypeList", {}).get("pubType", [])
            if isinstance(pub_type_list, list):
                pub_types = pub_type_list
            elif isinstance(pub_type_list, str):
                pub_types = [pub_type_list]

            # commentCorrectionList 추출
            comment_corrections = []
            cc_list = item.get("commentCorrectionList", {}).get("commentCorrection", [])
            if isinstance(cc_list, dict):
                cc_list = [cc_list]
            for cc in cc_list:
                if cc.get("id"):
                    comment_corrections.append(
                        CommentCorrection(
                            id=cc.get("id", ""),
                            type=cc.get("type", ""),
                            source=cc.get("source", ""),
                            reference=cc.get("reference", ""),
                        )
                    )

            results.append(
                SearchResult(
                    pmcid=pmcid,
                    pmid=item.get("pmid"),
                    doi=item.get("doi"),
                    title=item.get("title", ""),
                    is_open_access=item.get("isOpenAccess") == "Y",
                    pub_types=pub_types,
                    comment_corrections=comment_corrections,
                )
            )

        next_cursor = data.get("nextCursorMark")
        # 커서가 같으면 마지막 페이지
        if next_cursor == cursor:
            next_cursor = None

        return SearchPage(
            results=results,
            cursor=next_cursor,
            total_count=data.get("hitCount", 0),
            page_size=page_size,
        )

    async def search_all(
        self,
        query: str,
        page_size: int = 1000,
        max_results: int | None = None,
    ) -> AsyncIterator[SearchResult]:
        """모든 검색 결과 반복

        Args:
            query: 검색 쿼리
            page_size: 페이지 크기
            max_results: 최대 결과 수 (None = 무제한)

        Yields:
            SearchResult: 검색 결과
        """
        cursor = None
        collected = 0

        while True:
            page = await self.search(query, page_size, cursor)

            for result in page.results:
                if max_results and collected >= max_results:
                    return

                yield result
                collected += 1

            if not page.cursor:
                break

            cursor = page.cursor

            logger.info(
                "search_page_complete",
                collected=collected,
                total=page.total_count,
            )

    async def get_fulltext_xml(self, pmcid: str) -> str | None:
        """Fulltext XML 수집

        Args:
            pmcid: PMC ID (예: "PMC12345678")

        Returns:
            XML 문자열 또는 None (없는 경우)
        """
        original_pmcid = pmcid
        # PMC 접두사 제거
        if pmcid.startswith("PMC"):
            pmcid = pmcid[3:]

        url = f"{self.base_url}/PMC{pmcid}/fullTextXML"

        logger.debug(
            "fulltext_request_start",
            pmcid=original_pmcid,
            url=url,
        )

        try:
            response = await self._request("GET", url)
            text = response.text

            logger.debug(
                "fulltext_response_received",
                pmcid=original_pmcid,
                status=response.status_code,
                content_length=len(text) if text else 0,
                content_type=response.headers.get("content-type", "unknown"),
                preview=text[:200] if text else "(empty)",
            )

            # 빈 응답 체크
            if not text or len(text) < 100:
                logger.warning(
                    "fulltext_empty_response",
                    pmcid=original_pmcid,
                    status=response.status_code,
                    length=len(text) if text else 0,
                    preview=text[:200] if text else "(empty)",
                )
                return None

            # XML이 아닌 응답 체크 (HTML 에러 페이지 등)
            if not text.strip().startswith("<?xml") and not text.strip().startswith("<"):
                logger.warning(
                    "fulltext_not_xml",
                    pmcid=original_pmcid,
                    status=response.status_code,
                    content_type=response.headers.get("content-type", "unknown"),
                    preview=text[:500] if text else "(empty)",
                )
                return None

            return text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("fulltext_not_found", pmcid=original_pmcid)
                return None
            logger.error(
                "fulltext_http_error",
                pmcid=original_pmcid,
                status=e.response.status_code,
                response_preview=e.response.text[:500] if e.response.text else "(empty)",
            )
            raise
        except Exception as e:
            logger.error(
                "fulltext_fetch_error",
                pmcid=original_pmcid,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def get_stats(self) -> dict:
        """Rate Limiter 통계"""
        return self.rate_limiter.get_stats()

    async def get_citations(
        self,
        pmcid: str,
        page_size: int = 1000,
    ) -> CitationsPage:
        """논문을 인용한 논문 목록 조회 (Citations)

        Args:
            pmcid: PMC ID (예: "PMC12345678")
            page_size: 페이지 크기 (최대 1000)

        Returns:
            CitationsPage: 인용 목록
        """
        # PMC 접두사 제거
        if pmcid.startswith("PMC"):
            pmcid = pmcid[3:]

        params = {
            "format": "json",
            "pageSize": min(page_size, 1000),
        }

        url = f"{self.base_url}/PMC{pmcid}/citations"

        try:
            response = await self._request("GET", url, params=params)
            data = response.json()

            results = []
            citation_list = data.get("citationList", {}).get("citation", [])
            if isinstance(citation_list, dict):
                citation_list = [citation_list]

            for item in citation_list:
                # citedByPMCID, citedByPMID 등 추출
                results.append(
                    CitationResult(
                        pmcid=item.get("citedByPMCID"),
                        pmid=item.get("citedByPMID"),
                        doi=item.get("citedByDOI"),
                        title=item.get("title", ""),
                        source=item.get("source", ""),
                    )
                )

            total_count = data.get("hitCount", len(results))

            logger.info(
                "citations_fetched",
                pmcid=pmcid,
                count=len(results),
                total=total_count,
            )

            return CitationsPage(
                results=results,
                total_count=total_count,
                has_more=len(results) < total_count,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("citations_not_found", pmcid=pmcid)
                return CitationsPage(results=[], total_count=0)
            raise

    async def get_references(
        self,
        pmcid: str,
        page: int = 1,
        page_size: int = 1000,
    ) -> CitationsPage:
        """논문이 인용한 논문 목록 조회 (References)

        Args:
            pmcid: PMC ID (예: "PMC12345678")
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지 크기 (최대 1000)

        Returns:
            CitationsPage: 참조 목록
        """
        # PMC 접두사 제거
        if pmcid.startswith("PMC"):
            pmcid = pmcid[3:]

        params = {
            "format": "json",
            "page": page,
            "pageSize": min(page_size, 1000),
        }

        url = f"{self.base_url}/PMC{pmcid}/references"

        try:
            response = await self._request("GET", url, params=params)
            data = response.json()

            results = []
            ref_list = data.get("referenceList", {}).get("reference", [])
            if isinstance(ref_list, dict):
                ref_list = [ref_list]

            for item in ref_list:
                # PMCID가 있으면 사용, 없으면 id 필드(MED source인 경우 PMID)
                pmcid_val = item.get("pmcid")
                pmid_val = item.get("id") if item.get("source") == "MED" else None

                results.append(
                    CitationResult(
                        pmcid=pmcid_val,
                        pmid=pmid_val,
                        doi=item.get("doi"),
                        title=item.get("title", ""),
                        source=item.get("source", ""),
                    )
                )

            total_count = data.get("hitCount", len(results))

            logger.info(
                "references_fetched",
                pmcid=pmcid,
                count=len(results),
                total=total_count,
            )

            return CitationsPage(
                results=results,
                total_count=total_count,
                has_more=len(results) < total_count,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("references_not_found", pmcid=pmcid)
                return CitationsPage(results=[], total_count=0)
            raise
