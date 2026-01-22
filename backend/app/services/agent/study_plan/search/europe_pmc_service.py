"""Europe PMC Service - Tier 2 검색

Europe PMC REST API를 사용한 오픈 액세스 논문 검색
https://europepmc.org/RestfulWebService

주요 기능:
- 검색어 기반 논문 검색
- 오픈 액세스 필터링
- 전문(fulltext) XML 추출
"""

import logging
import hashlib
import httpx
from dataclasses import dataclass
from typing import Optional
import xml.etree.ElementTree as ET

from .types import EvidenceSnippetV3, SearchTier, ClaimType

logger = logging.getLogger(__name__)

EUROPE_PMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@dataclass
class EpmcSearchResult:
    """Europe PMC 검색 결과 아이템"""

    pmcid: str | None
    pmid: str | None
    doi: str | None
    title: str
    abstract: str
    journal: str
    year: int | None
    authors: str | None
    is_open_access: bool

    def to_evidence_snippet(
        self,
        claim_type: ClaimType = ClaimType.MECHANISM,
        relevance_score: float = 0.8,
    ) -> EvidenceSnippetV3:
        """EvidenceSnippetV3로 변환"""
        snippet_id = hashlib.md5(
            f"epmc:{self.pmcid or self.pmid}:{self.title[:50]}".encode()
        ).hexdigest()[:12]

        return EvidenceSnippetV3(
            snippet_id=f"epmc_{snippet_id}",
            text=self.abstract,
            source_tier=SearchTier.EPMC,
            source_tool="europe_pmc",
            claim_type=claim_type,
            paper_id=f"pmc:{self.pmcid}" if self.pmcid else None,
            pmc_id=self.pmcid,
            title=self.title,
            journal=self.journal,
            year=self.year,
            section="abstract",
            relevance_score=relevance_score,
        )


class EuropePmcService:
    """Europe PMC API 서비스

    Study Plan Agent v3 Tier 2 검색용
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        """HTTP 클라이언트 지연 초기화"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)

    async def search(
        self,
        query: str,
        open_access_only: bool = True,
        year_from: int | None = None,
        max_results: int = 20,
    ) -> list[EpmcSearchResult]:
        """Europe PMC 검색

        Args:
            query: 검색 쿼리 (자연어 또는 Europe PMC 쿼리 문법)
            open_access_only: 오픈 액세스 논문만 검색
            year_from: 특정 연도 이후 논문만 (예: 2018)
            max_results: 최대 결과 수 (최대 100)

        Returns:
            검색 결과 목록
        """
        await self._ensure_client()

        # 쿼리 빌드
        query_parts = [query]
        if open_access_only:
            query_parts.append("OPEN_ACCESS:y")
        if year_from:
            query_parts.append(f"PUB_YEAR:[{year_from} TO 2100]")

        full_query = " AND ".join(query_parts)

        params = {
            "query": full_query,
            "format": "json",
            "resultType": "core",
            "pageSize": min(max_results, 100),
            "sort": "relevance",
        }

        try:
            response = await self._client.get(
                f"{EUROPE_PMC_BASE_URL}/search", params=params
            )
            response.raise_for_status()
            data = response.json()

            results = []
            result_list = data.get("resultList", {}).get("result", [])

            for item in result_list:
                # 필수 필드 검증
                title = item.get("title", "").strip()
                if not title:
                    continue

                results.append(
                    EpmcSearchResult(
                        pmcid=item.get("pmcid"),
                        pmid=item.get("pmid"),
                        doi=item.get("doi"),
                        title=title,
                        abstract=item.get("abstractText", ""),
                        journal=item.get("journalTitle", ""),
                        year=self._parse_year(item.get("pubYear")),
                        authors=item.get("authorString"),
                        is_open_access=item.get("isOpenAccess") == "Y",
                    )
                )

            logger.info(
                "epmc_search query=%s results=%d open_access=%s",
                query[:50],
                len(results),
                open_access_only,
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error("epmc_search_http_error status=%d", e.response.status_code)
            return []
        except Exception as e:
            logger.error("epmc_search_error error=%s", str(e))
            return []

    async def get_fulltext_xml(
        self,
        pmc_id: str,
        sections: list[str] | None = None,
    ) -> dict[str, str]:
        """PMC 논문의 전문 XML에서 섹션 추출

        Args:
            pmc_id: PMC ID (예: "PMC12345678" 또는 "12345678")
            sections: 추출할 섹션 목록 (기본: methods, results)

        Returns:
            섹션별 텍스트 딕셔너리 {"methods": "...", "results": "..."}
        """
        await self._ensure_client()

        if sections is None:
            sections = ["methods", "results"]

        # PMC ID 정규화
        pmc_id = pmc_id.replace("PMC", "")

        try:
            response = await self._client.get(
                f"{EUROPE_PMC_BASE_URL}/PMC{pmc_id}/fullTextXML"
            )

            if response.status_code != 200:
                logger.warning("epmc_fulltext_not_found pmc_id=%s", pmc_id)
                return {}

            # XML 파싱
            root = ET.fromstring(response.text)

            result = {}
            for section in sections:
                text = self._extract_section(root, section)
                if text:
                    result[section] = text

            logger.info(
                "epmc_fulltext_extracted pmc_id=%s sections=%s",
                pmc_id,
                list(result.keys()),
            )
            return result

        except ET.ParseError as e:
            logger.error("epmc_xml_parse_error pmc_id=%s error=%s", pmc_id, str(e))
            return {}
        except Exception as e:
            logger.error("epmc_fulltext_error pmc_id=%s error=%s", pmc_id, str(e))
            return {}

    def _extract_section(self, root: ET.Element, section_type: str) -> str:
        """XML에서 특정 섹션 추출

        PMC XML 구조:
        - <sec sec-type="methods"> 또는 <sec><title>Methods</title>
        - <sec sec-type="results"> 또는 <sec><title>Results</title>
        """
        section_keywords = {
            "methods": [
                "methods",
                "materials and methods",
                "materials & methods",
                "experimental procedures",
            ],
            "results": ["results", "findings"],
            "discussion": ["discussion"],
            "conclusion": ["conclusion", "conclusions"],
        }

        keywords = section_keywords.get(section_type, [section_type])

        # 1. sec-type 속성으로 찾기
        for keyword in keywords:
            for sec in root.iter("sec"):
                sec_type = sec.get("sec-type", "").lower()
                if keyword in sec_type:
                    return self._get_section_text(sec)

        # 2. title 요소로 찾기
        for keyword in keywords:
            for sec in root.iter("sec"):
                title_elem = sec.find("title")
                if title_elem is not None and title_elem.text:
                    if keyword in title_elem.text.lower():
                        return self._get_section_text(sec)

        return ""

    def _get_section_text(self, section: ET.Element) -> str:
        """섹션 요소에서 텍스트 추출 (중첩 요소 포함)"""
        texts = []

        for elem in section.iter():
            if elem.tag in ("p", "title"):
                # 태그 내 모든 텍스트 (하위 요소 포함)
                text = "".join(elem.itertext()).strip()
                if text:
                    texts.append(text)

        return "\n\n".join(texts)

    async def search_and_extract(
        self,
        query: str,
        claim_type: ClaimType = ClaimType.MECHANISM,
        open_access_only: bool = True,
        year_from: int | None = None,
        max_results: int = 10,
        extract_fulltext: bool = False,
        fulltext_sections: list[str] | None = None,
    ) -> list[EvidenceSnippetV3]:
        """검색 + 전문 추출 통합

        Args:
            query: 검색 쿼리
            claim_type: Evidence 유형
            open_access_only: OA 필터
            year_from: 연도 필터
            max_results: 최대 결과 수
            extract_fulltext: 전문 추출 여부
            fulltext_sections: 추출할 섹션 (기본: methods, results)

        Returns:
            EvidenceSnippetV3 목록
        """
        # 1. 검색
        search_results = await self.search(
            query=query,
            open_access_only=open_access_only,
            year_from=year_from,
            max_results=max_results,
        )

        snippets = []

        for i, result in enumerate(search_results):
            # Abstract 기반 snippet
            relevance = 1.0 - (i * 0.05)  # 순서 기반 점수 감소
            snippet = result.to_evidence_snippet(
                claim_type=claim_type,
                relevance_score=max(relevance, 0.5),
            )
            snippets.append(snippet)

            # 전문 추출 (옵션)
            if extract_fulltext and result.pmcid and result.is_open_access:
                sections = await self.get_fulltext_xml(
                    result.pmcid, fulltext_sections
                )

                for section_name, section_text in sections.items():
                    if not section_text:
                        continue

                    # 섹션별 snippet 생성
                    section_snippet_id = hashlib.md5(
                        f"epmc:{result.pmcid}:{section_name}".encode()
                    ).hexdigest()[:12]

                    snippets.append(
                        EvidenceSnippetV3(
                            snippet_id=f"epmc_{section_snippet_id}",
                            text=section_text[:5000],  # 5000자 제한
                            source_tier=SearchTier.EPMC,
                            source_tool="europe_pmc",
                            claim_type=claim_type,
                            paper_id=f"pmc:{result.pmcid}",
                            pmc_id=result.pmcid,
                            title=result.title,
                            journal=result.journal,
                            year=result.year,
                            section=section_name,
                            relevance_score=relevance * 0.9,  # 전문은 약간 낮은 점수
                        )
                    )

        return snippets

    def _parse_year(self, year_str: str | None) -> int | None:
        """연도 문자열 파싱"""
        if not year_str:
            return None
        try:
            return int(year_str)
        except (ValueError, TypeError):
            return None

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 싱글톤 인스턴스
europe_pmc_service = EuropePmcService()
