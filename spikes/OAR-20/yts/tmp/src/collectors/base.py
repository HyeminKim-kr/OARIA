# -*- coding: utf-8 -*-
"""
논문 수집기 기본 인터페이스

모든 데이터 소스별 수집기가 구현해야 하는 기본 클래스입니다.
일관된 인터페이스를 통해 다양한 소스에서 동일한 방식으로 논문을 수집할 수 있습니다.

구현된 수집기:
- PubMedCollector: PubMed E-utilities API
- EuropePMCCollector: Europe PMC REST API (전문 수집 지원)
- OpenAlexCollector: OpenAlex API

작성자: yts
작성일: 2025-12-19
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """
    논문 수집기 추상 기본 클래스

    모든 데이터 소스별 수집기는 이 클래스를 상속받아
    search()와 get_full_text() 메서드를 구현해야 합니다.

    표준 논문 데이터 형식:
    {
        "id": "source:identifier",     # 고유 ID (예: "pubmed:12345678")
        "source": "pubmed",            # 데이터 소스명
        "pmid": "12345678",            # PubMed ID (있는 경우)
        "pmcid": "PMC12345678",        # PMC ID (있는 경우)
        "doi": "10.1234/...",          # DOI
        "title": "논문 제목",           # 제목
        "abstract": "초록 텍스트",      # 초록
        "authors": ["저자1", "저자2"],  # 저자 목록
        "year": 2024,                  # 출판 연도
        "journal": "저널명",            # 저널
        "keywords": ["키워드1", ...],   # 키워드/MeSH 용어
        "full_text_url": "https://...", # 전문 URL (있는 경우)
        "raw": {...}                   # 원본 API 응답 (디버깅용)
    }
    """

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        논문 검색 (추상 메서드 - 반드시 구현 필요)

        Args:
            query: 검색 쿼리 문자열
                   예: "lung cancer", "breast cancer treatment"
            limit: 최대 반환 결과 수 (기본값: 10)

        Returns:
            표준 형식의 논문 메타데이터 리스트:
            [
                {
                    "id": "source:identifier",
                    "source": "pubmed|europe_pmc|openalex",
                    "title": "논문 제목",
                    "abstract": "초록 텍스트",
                    "authors": ["저자1", "저자2", ...],
                    "year": 2024,
                    "doi": "10.1234/...",
                    "pmid": "12345678",
                    "journal": "저널명",
                    "keywords": ["키워드1", "키워드2", ...],
                    "full_text_url": "https://...",
                    "raw": {...}  # 원본 API 응답
                },
                ...
            ]

        Example:
            collector = EuropePMCCollector()
            papers = collector.search("lung cancer", limit=10)
            for paper in papers:
                print(f"{paper['title']} ({paper['year']})")
        """
        pass

    @abstractmethod
    def get_full_text(self, paper_id: str) -> str | None:
        """
        논문 전문 텍스트 수집 (추상 메서드 - 반드시 구현 필요)

        모든 소스가 전문을 제공하지는 않습니다.
        - Europe PMC: Open Access 논문의 전문 제공
        - PubMed: 전문 미제공 (PMC 연동 필요)
        - OpenAlex: 전문 미제공 (URL 링크만 제공)

        Args:
            paper_id: 논문 ID (소스별로 다름)
                      - PubMed: PMID (예: "12345678")
                      - Europe PMC: PMCID (예: "PMC12345678")
                      - OpenAlex: OpenAlex ID (예: "W1234567890")

        Returns:
            전문 텍스트 문자열 (성공 시)
            None (실패 시 또는 지원 안 하는 경우)

        Example:
            collector = EuropePMCCollector()
            full_text = collector.get_full_text("PMC12345678")
            if full_text:
                print(f"전문 길이: {len(full_text)} 글자")
            else:
                print("전문 수집 실패 또는 지원 안 함")
        """
        pass
