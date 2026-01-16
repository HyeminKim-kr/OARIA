"""유사 논문 추천 서비스

4가지 추천 방식:
1. Citation: 이 논문을 인용한 논문들 (Europe PMC API)
2. Reference: 이 논문이 인용한 논문들 (Europe PMC API)
3. Vector: 벡터 유사도 기반 (Weaviate)
4. Hybrid: 위 3가지 조합 (가중치 기반)
"""

import logging
import httpx
from dataclasses import dataclass
from typing import Optional

from .weaviate_service import weaviate_service

logger = logging.getLogger(__name__)

EUROPE_PMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@dataclass
class SimilarPaper:
    """유사 논문 아이템"""
    pmcid: Optional[str]
    pmid: Optional[str]
    doi: Optional[str]
    title: str
    journal: Optional[str] = None
    year: Optional[int] = None
    authors: Optional[str] = None
    recommendation_type: str = "citation"  # citation, reference, vector, hybrid
    score: float = 0.0
    sources: list[str] = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = []

    @property
    def unique_key(self) -> str:
        """중복 제거용 고유 키"""
        if self.pmcid:
            return f"pmc:{self.pmcid}"
        elif self.pmid:
            return f"pmid:{self.pmid}"
        elif self.doi:
            return f"doi:{self.doi}"
        return f"title:{self.title[:50]}"


class SimilarPapersService:
    """유사 논문 추천 서비스"""

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        """HTTP 클라이언트 초기화"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)

    async def get_citations(
        self,
        pmcid: Optional[str],
        pmid: Optional[str] = None,
        limit: int = 20
    ) -> list[SimilarPaper]:
        """이 논문을 인용한 논문들 (Citations)

        Europe PMC API 사용
        """
        await self._ensure_client()
        results = []

        # PMC ID로 시도
        if pmcid:
            pmcid_num = pmcid.replace("PMC", "")
            url = f"{EUROPE_PMC_BASE_URL}/PMC{pmcid_num}/citations"
            params = {"format": "json", "pageSize": limit}

            try:
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    citation_list = data.get("citationList", {}).get("citation", [])
                    if isinstance(citation_list, dict):
                        citation_list = [citation_list]

                    for item in citation_list:
                        results.append(SimilarPaper(
                            pmcid=item.get("citedByPMCID"),
                            pmid=item.get("citedByPMID") or item.get("id"),
                            doi=item.get("citedByDOI"),
                            title=item.get("title", ""),
                            journal=item.get("journalAbbreviation"),
                            year=self._parse_year(item.get("pubYear")),
                            recommendation_type="citation",
                            score=1.0,
                        ))
            except Exception as e:
                logger.warning("citations_fetch_error pmcid=%s error=%s", pmcid, str(e))

        # PMID로도 시도 (PMC 결과가 없을 때)
        if not results and pmid:
            url = f"{EUROPE_PMC_BASE_URL}/MED/{pmid}/citations"
            params = {"format": "json", "pageSize": limit}

            try:
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    citation_list = data.get("citationList", {}).get("citation", [])
                    if isinstance(citation_list, dict):
                        citation_list = [citation_list]

                    for item in citation_list:
                        results.append(SimilarPaper(
                            pmcid=item.get("pmcid"),
                            pmid=item.get("id"),
                            doi=item.get("doi"),
                            title=item.get("title", ""),
                            journal=item.get("journalAbbreviation"),
                            year=self._parse_year(item.get("pubYear")),
                            recommendation_type="citation",
                            score=1.0,
                        ))
            except Exception as e:
                logger.warning("citations_fetch_error_med pmid=%s error=%s", pmid, str(e))

        return results

    async def get_references(
        self,
        pmcid: Optional[str],
        pmid: Optional[str] = None,
        limit: int = 20
    ) -> list[SimilarPaper]:
        """이 논문이 인용한 논문들 (References)

        Europe PMC API 사용
        """
        await self._ensure_client()
        results = []

        # PMC ID로 시도
        if pmcid:
            pmcid_num = pmcid.replace("PMC", "")
            url = f"{EUROPE_PMC_BASE_URL}/PMC{pmcid_num}/references"
            params = {"format": "json", "pageSize": limit}

            try:
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    ref_list = data.get("referenceList", {}).get("reference", [])
                    if isinstance(ref_list, dict):
                        ref_list = [ref_list]

                    for item in ref_list:
                        results.append(SimilarPaper(
                            pmcid=item.get("pmcid"),
                            pmid=item.get("id") if item.get("source") == "MED" else None,
                            doi=item.get("doi"),
                            title=item.get("title", ""),
                            journal=item.get("journalAbbreviation"),
                            year=self._parse_year(item.get("pubYear")),
                            recommendation_type="reference",
                            score=0.8,
                        ))
            except Exception as e:
                logger.warning("references_fetch_error pmcid=%s error=%s", pmcid, str(e))

        # PMID로도 시도
        if not results and pmid:
            url = f"{EUROPE_PMC_BASE_URL}/MED/{pmid}/references"
            params = {"format": "json", "pageSize": limit}

            try:
                response = await self.client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    ref_list = data.get("referenceList", {}).get("reference", [])
                    if isinstance(ref_list, dict):
                        ref_list = [ref_list]

                    for item in ref_list:
                        results.append(SimilarPaper(
                            pmcid=item.get("pmcid"),
                            pmid=item.get("id"),
                            doi=item.get("doi"),
                            title=item.get("title", ""),
                            journal=item.get("journalAbbreviation"),
                            year=self._parse_year(item.get("pubYear")),
                            recommendation_type="reference",
                            score=0.8,
                        ))
            except Exception as e:
                logger.warning("references_fetch_error_med pmid=%s error=%s", pmid, str(e))

        return results

    async def get_vector_similar(
        self,
        paper_id: str,
        limit: int = 10
    ) -> list[SimilarPaper]:
        """벡터 유사도 기반 유사 논문 (Weaviate)

        Abstract 청크를 기반으로 유사 논문 검색
        """
        try:
            # 현재 논문의 abstract 청크 가져오기
            chunks = weaviate_service.get_chunks_by_paper_and_section(paper_id, "abstract")
            if not chunks:
                logger.warning("no_abstract_chunk paper_id=%s", paper_id)
                return []

            # 첫 번째 청크의 텍스트로 유사 검색
            first_chunk = chunks[0]
            query_text = first_chunk.get("text", "")
            if not query_text:
                return []

            # Weaviate에서 유사 청크 검색
            similar_chunks = weaviate_service.search_similar(
                query_text=query_text,
                limit=limit * 2,  # 중복 제거 여유분
            )

            # 논문별로 그룹화하고 가장 높은 점수 사용
            paper_scores: dict[str, SimilarPaper] = {}

            for chunk in similar_chunks:
                chunk_paper_id = chunk.get("paper_id", "")

                # 원본 논문 제외
                if chunk_paper_id == paper_id:
                    continue

                # PMCID 추출 (pmc:PMC12345678 → PMC12345678)
                pmcid = None
                if chunk_paper_id.startswith("pmc:"):
                    pmcid = chunk_paper_id[4:]

                distance = chunk.get("distance", 1.0)
                score = 1.0 - distance  # distance를 유사도로 변환

                if chunk_paper_id not in paper_scores or score > paper_scores[chunk_paper_id].score:
                    paper_scores[chunk_paper_id] = SimilarPaper(
                        pmcid=pmcid,
                        pmid=None,
                        doi=None,
                        title=chunk.get("title", ""),
                        journal=chunk.get("journal"),
                        year=chunk.get("year"),
                        recommendation_type="vector",
                        score=score,
                    )

            # 점수순 정렬
            results = sorted(paper_scores.values(), key=lambda x: x.score, reverse=True)
            return results[:limit]

        except Exception as e:
            logger.warning("vector_similar_error paper_id=%s error=%s", paper_id, str(e))
            return []

    def create_hybrid(
        self,
        citations: list[SimilarPaper],
        references: list[SimilarPaper],
        vector_similar: list[SimilarPaper],
    ) -> list[SimilarPaper]:
        """하이브리드 추천 생성 (중복 제거 및 가중치 기반 점수화)

        가중치:
        - Citation: 1.0 (최신 후속 연구)
        - Reference: 0.8 (기반 연구)
        - Vector: 0.6 + score (내용 유사도)
        """
        paper_scores: dict[str, dict] = {}

        def add_paper(paper: SimilarPaper, source_weight: float, source_type: str):
            key = paper.unique_key
            if key not in paper_scores:
                paper_scores[key] = {
                    "paper": paper,
                    "sources": [],
                    "total_score": 0.0,
                }
            paper_scores[key]["sources"].append(source_type)
            paper_scores[key]["total_score"] += source_weight + paper.score

        # 각 소스별 가중치 적용
        for paper in citations:
            add_paper(paper, 1.0, "citation")

        for paper in references:
            add_paper(paper, 0.8, "reference")

        for paper in vector_similar:
            add_paper(paper, 0.6, "vector")

        # 점수순 정렬 (소스 개수 우선, 그 다음 점수)
        sorted_papers = sorted(
            paper_scores.values(),
            key=lambda x: (len(x["sources"]), x["total_score"]),
            reverse=True
        )

        results = []
        for item in sorted_papers[:20]:
            paper = item["paper"]
            paper.recommendation_type = "hybrid"
            paper.score = item["total_score"]
            paper.sources = sorted(set(item["sources"]))
            results.append(paper)

        return results

    async def get_similar_papers(
        self,
        paper_id: str,
        pmcid: Optional[str],
        pmid: Optional[str],
        source: str = "hybrid",
        limit: int = 20
    ) -> tuple[list[SimilarPaper], str]:
        """유사 논문 조회 (통합 인터페이스)

        Args:
            paper_id: 논문 ID (pmc:PMC12345678 형식)
            pmcid: PMC ID (PMC12345678)
            pmid: PubMed ID
            source: 추천 소스 (citation, reference, vector, hybrid)
            limit: 결과 개수

        Returns:
            tuple: (유사 논문 목록, 소스 타입)
        """
        if source == "citation":
            results = await self.get_citations(pmcid, pmid, limit)
            return results, "citation"

        elif source == "reference":
            results = await self.get_references(pmcid, pmid, limit)
            return results, "reference"

        elif source == "vector":
            results = await self.get_vector_similar(paper_id, limit)
            return results, "vector"

        else:  # hybrid
            # 모든 소스에서 조회
            citations = await self.get_citations(pmcid, pmid, limit)
            references = await self.get_references(pmcid, pmid, limit)
            vector_similar = await self.get_vector_similar(paper_id, min(limit, 10))

            # 하이브리드 생성
            results = self.create_hybrid(citations, references, vector_similar)
            return results[:limit], "hybrid"

    def _parse_year(self, year_str: Optional[str]) -> Optional[int]:
        """연도 문자열을 정수로 변환"""
        if not year_str:
            return None
        try:
            return int(year_str)
        except (ValueError, TypeError):
            return None

    async def close(self):
        """클라이언트 종료"""
        if self.client:
            await self.client.aclose()
            self.client = None


# 싱글톤 인스턴스
similar_papers_service = SimilarPapersService()
