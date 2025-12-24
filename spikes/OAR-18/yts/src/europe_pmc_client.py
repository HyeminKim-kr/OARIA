# -*- coding: utf-8 -*-
"""
Europe PMC API Client - 전문(Full-text) 수집 지원

암 논문 수집을 위한 Europe PMC REST API 클라이언트
PubMed 대신 Europe PMC를 사용하는 이유: Open Access 전문(Full-text) 무료 제공

사용법:
    # 메타데이터만 수집
    uv run python -m src.europe_pmc_client search "lung cancer" --limit 10

    # 전문 포함 수집
    uv run python -m src.europe_pmc_client fulltext "breast cancer" --limit 5

작성자: yts
작성일: 2025-12-22
"""

import re
import time
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

import httpx


@dataclass
class Paper:
    """논문 메타데이터"""
    id: str                          # europepmc:PMC12345678
    source: str                      # europe_pmc
    pmid: Optional[str]
    pmcid: Optional[str]
    doi: Optional[str]
    title: str
    abstract: Optional[str]
    authors: list[str]
    journal: Optional[str]
    year: Optional[int]
    keywords: list[str]
    mesh_terms: list[str]
    is_open_access: bool
    has_full_text: bool
    full_text: Optional[str] = None           # 전문 텍스트
    full_text_sections: Optional[dict] = None  # 섹션별 텍스트


class EuropePMCClient:
    """
    Europe PMC REST API 클라이언트

    특징:
    - Open Access 논문의 전문(XML) 수집 가능
    - 인증 불필요
    - 암 논문 약 530만건 보유 (그 중 OA 약 200만건)
    """

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, delay: float = 0.3):
        """
        Args:
            delay: API 호출 간 딜레이 (초). 기본값 0.3초.
        """
        self.client = httpx.Client(timeout=60.0)
        self.delay = delay
        self._last_request_time = 0

    def _rate_limit(self):
        """Rate limit 준수를 위한 딜레이"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    # ============================================================
    # 검색 메서드
    # ============================================================

    def search(
        self,
        query: str,
        limit: int = 10,
        open_access_only: bool = True,
        cursor: str = "*"
    ) -> dict:
        """
        논문 검색 (메타데이터 + 초록)

        Args:
            query: 검색 쿼리 (예: "lung cancer", "neoplasms")
            limit: 최대 결과 수 (max 1000)
            open_access_only: Open Access 논문만 검색
            cursor: 페이지네이션 커서

        Returns:
            {
                "papers": [Paper, ...],
                "next_cursor": str,
                "hit_count": int,
                "query": str
            }
        """
        if open_access_only:
            query = f"{query} AND OPEN_ACCESS:Y"

        params = {
            "query": query,
            "format": "json",
            "pageSize": min(limit, 1000),
            "cursorMark": cursor,
            "resultType": "core"
        }

        self._rate_limit()

        url = f"{self.BASE_URL}/search"
        response = self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        results = data.get("resultList", {}).get("result", [])

        papers = [self._parse_result(item) for item in results]
        papers = [p for p in papers if p is not None]

        return {
            "papers": papers,
            "next_cursor": data.get("nextCursorMark"),
            "hit_count": data.get("hitCount", 0),
            "query": query
        }

    def search_with_fulltext(
        self,
        query: str,
        limit: int = 10,
        verbose: bool = True
    ) -> list[Paper]:
        """
        논문 검색 + 전문 수집 (Open Access 논문만)

        Args:
            query: 검색 쿼리
            limit: 최대 결과 수
            verbose: 진행 상황 출력 여부

        Returns:
            전문이 포함된 Paper 리스트
        """
        result = self.search(query, limit=limit, open_access_only=True)
        papers = result["papers"]

        for i, paper in enumerate(papers):
            if paper.pmcid:
                if verbose:
                    print(f"  [{i+1}/{len(papers)}] 전문 수집: {paper.pmcid}")

                full_text = self.get_full_text(paper.pmcid)
                paper.full_text = full_text
                paper.full_text_sections = self._parse_sections(full_text) if full_text else None

                time.sleep(self.delay)

        return papers

    # ============================================================
    # 전문 수집 메서드
    # ============================================================

    def get_full_text(self, pmcid: str) -> Optional[str]:
        """
        PMC ID로 논문 전문 수집

        Args:
            pmcid: PMC ID (예: "PMC12345678" 또는 "12345678")

        Returns:
            전문 텍스트 (성공 시) 또는 None (실패 시)
        """
        if not pmcid:
            return None

        pmcid = pmcid.replace("PMC", "")
        url = f"{self.BASE_URL}/PMC{pmcid}/fullTextXML"

        try:
            self._rate_limit()
            response = self.client.get(url)
            response.raise_for_status()
            xml_text = response.text
            return self._xml_to_text(xml_text)

        except httpx.HTTPError as e:
            print(f"  전문 수집 실패 ({pmcid}): {e}")
            return None

    # ============================================================
    # 내부 헬퍼 메서드
    # ============================================================

    def _parse_result(self, item: dict) -> Optional[Paper]:
        """API 응답을 Paper 객체로 변환"""
        try:
            pmid = item.get("pmid", "")
            pmcid = item.get("pmcid", "")
            source_id = pmcid or pmid

            # 저자 목록
            authors = []
            author_list = item.get("authorList", {}).get("author", [])
            for author in author_list:
                full_name = author.get("fullName", "")
                if full_name:
                    authors.append(full_name)

            # 출판 연도
            year = item.get("pubYear")
            try:
                year = int(year) if year else None
            except ValueError:
                year = None

            # 키워드
            keywords = item.get("keywordList", {}).get("keyword", [])
            if isinstance(keywords, list):
                keywords = keywords[:20]

            # MeSH 용어
            mesh_terms = []
            mesh_list = item.get("meshHeadingList", {}).get("meshHeading", [])
            for mesh in mesh_list:
                if isinstance(mesh, dict):
                    name = mesh.get("descriptorName", "")
                    if name:
                        mesh_terms.append(name)

            return Paper(
                id=f"europepmc:{source_id}",
                source="europe_pmc",
                pmid=pmid,
                pmcid=pmcid,
                doi=item.get("doi", ""),
                title=item.get("title", ""),
                abstract=item.get("abstractText"),
                authors=authors,
                journal=item.get("journalTitle"),
                year=year,
                keywords=keywords,
                mesh_terms=mesh_terms,
                is_open_access=item.get("isOpenAccess", "N") == "Y",
                # hasFullText 필드가 없음 → inEPMC 또는 pmcid로 전문 가용 여부 판단
                has_full_text=(
                    item.get("inEPMC", "N") == "Y" or
                    item.get("inPMC", "N") == "Y" or
                    bool(item.get("pmcid"))
                ),
            )

        except Exception as e:
            print(f"파싱 에러: {e}")
            return None

    def _xml_to_text(self, xml: str) -> str:
        """XML에서 태그 제거하여 플레인 텍스트 추출"""
        text = re.sub(r'<[^>]+>', ' ', xml)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_sections(self, full_text: str) -> Optional[dict]:
        """전문을 섹션별로 분리"""
        if not full_text:
            return None

        sections = {
            "abstract": "",
            "introduction": "",
            "methods": "",
            "results": "",
            "discussion": "",
            "conclusion": "",
            "full": full_text[:50000],  # 50K 제한
        }

        text_lower = full_text.lower()

        section_markers = [
            ("abstract", ["abstract"]),
            ("introduction", ["introduction", "background"]),
            ("methods", ["methods", "materials and methods", "methodology"]),
            ("results", ["results"]),
            ("discussion", ["discussion"]),
            ("conclusion", ["conclusion", "conclusions"]),
        ]

        for section_name, markers in section_markers:
            for marker in markers:
                idx = text_lower.find(marker)
                if idx != -1:
                    sections[section_name] = full_text[idx:idx+2000].strip()
                    break

        return sections

    def __del__(self):
        """소멸자: HTTP 클라이언트 정리"""
        if hasattr(self, 'client'):
            self.client.close()


# ============================================================
# CLI
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Europe PMC 논문 수집기")
    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # search 명령
    search_parser = subparsers.add_parser("search", help="메타데이터 검색")
    search_parser.add_argument("query", help="검색 쿼리")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="최대 결과 수")
    search_parser.add_argument("--save", "-s", action="store_true", help="JSON 파일 저장")

    # fulltext 명령
    fulltext_parser = subparsers.add_parser("fulltext", help="전문 포함 검색")
    fulltext_parser.add_argument("query", help="검색 쿼리")
    fulltext_parser.add_argument("--limit", "-l", type=int, default=5, help="최대 결과 수")
    fulltext_parser.add_argument("--save", "-s", action="store_true", help="JSON 파일 저장")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    client = EuropePMCClient()

    if args.command == "search":
        print(f"\n=== Europe PMC 검색 ===")
        print(f"쿼리: {args.query}")
        print(f"최대: {args.limit}건\n")

        result = client.search(args.query, limit=args.limit)

        print(f"총 결과: {result['hit_count']:,}건")
        print(f"조회됨: {len(result['papers'])}건\n")

        for i, paper in enumerate(result['papers'], 1):
            print(f"{i}. [{paper.pmcid or paper.pmid}] {paper.title[:60]}...")
            print(f"   저자: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}")
            print(f"   저널: {paper.journal} ({paper.year})")
            print(f"   OA: {'Yes' if paper.is_open_access else 'No'} | 전문: {'Yes' if paper.has_full_text else 'No'}")
            print()

        if args.save:
            save_path = Path("samples") / f"search_{args.query.replace(' ', '_')}_{args.limit}.json"
            save_path.parent.mkdir(exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump([asdict(p) for p in result['papers']], f, ensure_ascii=False, indent=2)
            print(f"저장됨: {save_path}")

    elif args.command == "fulltext":
        print(f"\n=== Europe PMC 전문 수집 ===")
        print(f"쿼리: {args.query} AND OPEN_ACCESS:Y")
        print(f"최대: {args.limit}건\n")

        papers = client.search_with_fulltext(args.query, limit=args.limit)

        fulltext_count = sum(1 for p in papers if p.full_text)
        print(f"\n=== 결과 ===")
        print(f"전체: {len(papers)}건")
        print(f"전문 수집: {fulltext_count}건\n")

        for i, paper in enumerate(papers, 1):
            has_ft = "Yes" if paper.full_text else "No"
            ft_len = len(paper.full_text) if paper.full_text else 0
            print(f"{i}. [{paper.pmcid}] {paper.title[:50]}...")
            print(f"   전문: {has_ft} ({ft_len:,} chars)")
            if paper.full_text_sections:
                sections = [k for k, v in paper.full_text_sections.items() if v and k != 'full']
                print(f"   섹션: {', '.join(sections)}")
            print()

        if args.save:
            save_path = Path("samples") / f"fulltext_{args.query.replace(' ', '_')}_{args.limit}.json"
            save_path.parent.mkdir(exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump([asdict(p) for p in papers], f, ensure_ascii=False, indent=2)
            print(f"저장됨: {save_path}")


if __name__ == "__main__":
    main()
