# -*- coding: utf-8 -*-
"""
Europe PMC Collector - Open Access 전문 수집 지원

Europe PMC는 생의학 논문의 메타데이터와 Open Access 전문을 제공하는 서비스입니다.
이 모듈은 Europe PMC REST API를 사용하여 논문을 검색하고 전문을 수집합니다.

주요 기능:
- search(): 메타데이터 + 초록 검색
- search_with_fulltext(): 메타데이터 + 초록 + 전문 수집 (OA 논문만)
- get_full_text(): 개별 논문 전문 수집

API 문서: https://europepmc.org/RestfulWebService

작성자: yts
작성일: 2025-12-19
"""

import re
import time
from typing import Any

import httpx

from .base import BaseCollector


class EuropePMCCollector(BaseCollector):
    """
    Europe PMC REST API를 사용한 논문 수집기

    특징:
    - Open Access 논문의 전문(XML) 수집 가능
    - 인증 불필요
    - 암 논문 약 530만건 보유 (그 중 OA 약 200만건)

    사용 예시:
        collector = EuropePMCCollector(delay=0.5)

        # 메타데이터만 수집
        papers = collector.search("lung cancer", limit=10)

        # 전문 포함 수집
        papers = collector.search_with_fulltext("lung cancer", limit=10)
    """

    # Europe PMC REST API 기본 URL
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, delay: float = 0.5):
        """
        Europe PMC Collector 초기화

        Args:
            delay: API 호출 간 딜레이 (초). 기본값 0.5초.
                   API 서버 부하 방지를 위해 적절한 딜레이 필요.
        """
        # HTTP 클라이언트 (타임아웃 60초 - 전문 수집 시 오래 걸릴 수 있음)
        self.client = httpx.Client(timeout=60.0)
        self.delay = delay

    # ============================================================
    # 검색 메서드
    # ============================================================

    def search(
        self,
        query: str,
        limit: int = 10,
        open_access_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Europe PMC에서 논문 검색 (메타데이터 + 초록만)

        Args:
            query: 검색 쿼리 (예: "lung cancer", "breast cancer treatment")
            limit: 최대 결과 수 (기본값: 10)
            open_access_only: True면 Open Access 논문만 검색 (기본값: True)
                              전문 수집이 필요하면 True로 설정

        Returns:
            논문 메타데이터 리스트. 각 논문은 표준화된 딕셔너리 형태:
            {
                "id": "europepmc:PMC12345678",
                "source": "europe_pmc",
                "pmid": "12345678",
                "pmcid": "PMC12345678",
                "title": "논문 제목",
                "abstract": "초록 텍스트",
                "authors": ["저자1", "저자2"],
                "year": 2024,
                ...
            }
        """
        # Open Access 필터 추가
        if open_access_only:
            query = f"{query} AND OPEN_ACCESS:Y"

        # API 요청 파라미터
        url = f"{self.BASE_URL}/search"
        params = {
            "query": query,
            "format": "json",
            "pageSize": limit,
            "resultType": "core",  # 상세 메타데이터 포함
        }

        # API 호출
        response = self.client.get(url, params=params)
        response.raise_for_status()

        # 결과 파싱
        data = response.json()
        results = data.get("resultList", {}).get("result", [])

        # 각 결과를 표준 형식으로 변환
        papers = []
        for item in results:
            paper = self._parse_result(item)
            if paper:
                papers.append(paper)

        return papers

    def search_with_fulltext(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        논문 검색 + 전문 수집 (Open Access 논문만)

        search()로 검색한 후 각 논문의 전문을 추가로 수집합니다.
        전문 수집은 논문당 1회 API 호출이 필요하므로 시간이 오래 걸릴 수 있습니다.

        Args:
            query: 검색 쿼리
            limit: 최대 결과 수

        Returns:
            논문 리스트 (각 논문에 full_text, full_text_sections 필드 추가)
            {
                ...기존 메타데이터...,
                "full_text": "전문 텍스트 전체",
                "full_text_sections": {
                    "abstract": "...",
                    "introduction": "...",
                    "methods": "...",
                    "results": "...",
                    "discussion": "...",
                    "conclusion": "...",
                    "full": "전체 텍스트 (50K 제한)"
                }
            }
        """
        # 1단계: OA 논문 검색
        papers = self.search(query, limit=limit, open_access_only=True)

        # 2단계: 각 논문의 전문 수집
        for i, paper in enumerate(papers):
            pmcid = paper.get("pmcid")
            if pmcid:
                # 진행 상황 출력
                print(f"  [{i+1}/{len(papers)}] 전문 수집 중: {pmcid}")

                # 전문 수집
                full_text = self.get_full_text(pmcid)
                paper["full_text"] = full_text

                # 섹션별 파싱
                paper["full_text_sections"] = self._parse_sections(full_text) if full_text else None

                # API 부하 방지를 위한 딜레이
                time.sleep(self.delay)

        return papers

    # ============================================================
    # 전문 수집 메서드
    # ============================================================

    def get_full_text(self, pmcid: str) -> str | None:
        """
        PMC ID로 논문 전문 수집

        Europe PMC의 fullTextXML API를 호출하여 XML을 받아온 후
        태그를 제거하여 순수 텍스트로 변환합니다.

        Args:
            pmcid: PMC ID (예: "PMC12345678" 또는 "12345678")

        Returns:
            전문 텍스트 (성공 시) 또는 None (실패 시)

        Note:
            Open Access 논문만 전문 수집 가능합니다.
            비 OA 논문은 403 에러가 발생합니다.
        """
        if not pmcid:
            return None

        # PMCID 정규화 (PMC 접두사 처리)
        pmcid = pmcid.replace("PMC", "")
        url = f"{self.BASE_URL}/PMC{pmcid}/fullTextXML"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            xml_text = response.text

            # XML → 플레인 텍스트 변환
            return self._xml_to_text(xml_text)

        except httpx.HTTPError as e:
            print(f"전문 수집 실패 ({pmcid}): {e}")
            return None

    # ============================================================
    # 내부 헬퍼 메서드
    # ============================================================

    def _parse_result(self, item: dict) -> dict[str, Any] | None:
        """
        Europe PMC API 응답을 표준 형식으로 변환

        Args:
            item: API 응답의 개별 논문 데이터

        Returns:
            표준화된 논문 딕셔너리 또는 None (파싱 실패 시)
        """
        try:
            # === 기본 ID ===
            pmid = item.get("pmid", "")
            pmcid = item.get("pmcid", "")
            source_id = pmcid or pmid  # PMCID 우선

            # === 기본 메타데이터 ===
            title = item.get("title", "")
            abstract = item.get("abstractText", "")

            # === 저자 목록 ===
            authors = []
            author_list = item.get("authorList", {}).get("author", [])
            for author in author_list:
                full_name = author.get("fullName", "")
                if full_name:
                    authors.append(full_name)

            # === 출판 연도 ===
            year = item.get("pubYear")
            try:
                year = int(year) if year else None
            except ValueError:
                year = None

            # === 저널 정보 ===
            journal_info = item.get("journalInfo", {})
            journal = journal_info.get("journal", {}).get("title", "")

            # === DOI ===
            doi = item.get("doi", "")

            # === 키워드 ===
            keywords = []
            keyword_list = item.get("keywordList", {}).get("keyword", [])
            if isinstance(keyword_list, list):
                keywords = keyword_list[:20]  # 상위 20개로 제한

            # === MeSH 의료 용어 ===
            mesh_terms = []
            mesh_list = item.get("meshHeadingList", {}).get("meshHeading", [])
            for mesh in mesh_list:
                if isinstance(mesh, dict):
                    name = mesh.get("descriptorName", "")
                    if name:
                        mesh_terms.append(name)

            # === URL 생성 ===
            full_text_url = None
            pdf_url = None
            if pmcid:
                pmc_number = pmcid.replace("PMC", "")
                full_text_url = f"https://europepmc.org/article/PMC/{pmc_number}"
                pdf_url = f"https://europepmc.org/article/PMC/{pmc_number}?pdf=render"

            # === Open Access 여부 ===
            is_open_access = item.get("isOpenAccess", "N") == "Y"

            # === 라이선스 ===
            license_type = item.get("license", "")

            # 표준 형식으로 반환
            return {
                "id": f"europepmc:{source_id}",
                "source": "europe_pmc",
                "pmid": pmid,
                "pmcid": pmcid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "year": year,
                "journal": journal,
                "keywords": keywords,
                "mesh_terms": mesh_terms,
                "is_open_access": is_open_access,
                "license": license_type,
                "full_text_url": full_text_url,
                "pdf_url": pdf_url,
                "raw": item,  # 원본 데이터 보존
            }

        except Exception as e:
            print(f"파싱 에러: {e}")
            return None

    def _xml_to_text(self, xml: str) -> str:
        """
        XML 문서에서 태그를 제거하고 순수 텍스트 추출

        Args:
            xml: XML 문자열

        Returns:
            태그가 제거된 플레인 텍스트
        """
        # XML 태그 제거 (정규식 사용)
        text = re.sub(r'<[^>]+>', ' ', xml)

        # 연속 공백 정규화
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _parse_sections(self, full_text: str) -> dict[str, str] | None:
        """
        전문 텍스트를 섹션별로 분리

        논문의 일반적인 섹션 구조를 기반으로 텍스트를 분리합니다.
        간단한 키워드 기반 추출이므로 완벽하지 않을 수 있습니다.

        Args:
            full_text: 전문 텍스트

        Returns:
            섹션별 텍스트 딕셔너리:
            {
                "abstract": "초록 내용...",
                "introduction": "서론 내용...",
                "methods": "방법론 내용...",
                "results": "결과 내용...",
                "discussion": "토론 내용...",
                "conclusion": "결론 내용...",
                "full": "전체 텍스트 (50K 제한)"
            }
        """
        if not full_text:
            return None

        # 결과 딕셔너리 초기화
        sections = {
            "abstract": "",
            "introduction": "",
            "methods": "",
            "results": "",
            "discussion": "",
            "conclusion": "",
            "full": full_text[:50000],  # 전체 텍스트는 50K로 제한 (토큰 절약)
        }

        text_lower = full_text.lower()

        # 섹션 마커 정의 (섹션명 → 검색할 키워드들)
        section_markers = [
            ("abstract", ["abstract"]),
            ("introduction", ["introduction", "background"]),
            ("methods", ["methods", "materials and methods", "methodology"]),
            ("results", ["results"]),
            ("discussion", ["discussion"]),
            ("conclusion", ["conclusion", "conclusions"]),
        ]

        # 각 섹션의 시작 위치를 찾아 내용 추출
        # (단순화된 구현 - 실제로는 XML 파싱이 더 정확함)
        for section_name, markers in section_markers:
            for marker in markers:
                idx = text_lower.find(marker)
                if idx != -1:
                    # 마커 이후 약 2000자 추출
                    sections[section_name] = full_text[idx:idx+2000].strip()
                    break

        return sections

    def __del__(self):
        """소멸자: HTTP 클라이언트 정리"""
        self.client.close()
