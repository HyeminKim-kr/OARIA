"""
파이프라인 모듈

검색 → 수집 → 파싱 → 저장 통합 파이프라인
"""

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import Config
from .europe_pmc_client import AsyncEuropePMCClient, PaperInfo
from .parser import PaperParser
from .storage import DatabaseStorage, S3Storage
from .models import ParsedPaper


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""
    total: int = 0
    success: int = 0
    failed: int = 0
    papers: list[ParsedPaper] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


class Pipeline:
    """논문 수집 파이프라인

    검색 → 수집 → 파싱 → 저장 전체 흐름 관리
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self.parser = PaperParser()
        self.db = DatabaseStorage(self.config)
        self.s3 = S3Storage(self.config)

    async def run(
        self,
        query: str,
        limit: int = 10,
        max_concurrent: int = 10,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        save_to_db: bool = True,
        save_to_s3: bool = True,
    ) -> PipelineResult:
        """파이프라인 실행

        Args:
            query: 검색 쿼리 (예: "lung cancer")
            limit: 최대 수집 수
            max_concurrent: 동시 수집 수
            on_progress: 진행 콜백 (completed, total, pmcid)
            save_to_db: PostgreSQL 저장 여부
            save_to_s3: S3 저장 여부

        Returns:
            PipelineResult
        """
        result = PipelineResult()

        # 1. 검색
        async with AsyncEuropePMCClient(
            max_concurrent=max_concurrent,
            delay=self.config.api.delay,
            timeout=self.config.api.timeout,
        ) as client:
            papers = await client.search(query, limit=limit, open_access_only=True)

        if not papers:
            return result

        # PMCID가 있는 논문만 필터링
        papers_with_pmcid = [p for p in papers if p.pmcid]
        result.total = len(papers_with_pmcid)

        if not papers_with_pmcid:
            return result

        # 2. 수집 (병렬)
        pmcids = [p.pmcid for p in papers_with_pmcid]

        async with AsyncEuropePMCClient(
            max_concurrent=max_concurrent,
            delay=self.config.api.delay,
            timeout=self.config.api.timeout,
        ) as client:
            xml_results = await client.get_fulltext_xml_batch(
                pmcids,
                on_progress=on_progress,
            )

        # 3. 파싱 + 저장
        if save_to_db:
            async with self.db.connect():
                for pmcid, xml in xml_results.items():
                    if not xml:
                        result.failed += 1
                        result.errors.append({
                            "pmcid": pmcid,
                            "error": "XML 수집 실패",
                        })
                        continue

                    try:
                        parsed = self.parser.parse(xml)
                        result.papers.append(parsed)

                        # DB 저장
                        await self.db.save_all(parsed)

                        # S3 저장
                        if save_to_s3:
                            self.s3.save_all(parsed)

                        result.success += 1

                    except Exception as e:
                        result.failed += 1
                        result.errors.append({
                            "pmcid": pmcid,
                            "error": str(e),
                        })
        else:
            # DB 저장 없이 파싱만
            for pmcid, xml in xml_results.items():
                if not xml:
                    result.failed += 1
                    result.errors.append({
                        "pmcid": pmcid,
                        "error": "XML 수집 실패",
                    })
                    continue

                try:
                    parsed = self.parser.parse(xml)
                    result.papers.append(parsed)

                    if save_to_s3:
                        self.s3.save_all(parsed)

                    result.success += 1

                except Exception as e:
                    result.failed += 1
                    result.errors.append({
                        "pmcid": pmcid,
                        "error": str(e),
                    })

        return result

    async def collect_single(
        self,
        pmcid: str,
        save_to_db: bool = True,
        save_to_s3: bool = True,
    ) -> ParsedPaper | None:
        """단일 논문 수집

        Args:
            pmcid: PMC ID
            save_to_db: PostgreSQL 저장 여부
            save_to_s3: S3 저장 여부

        Returns:
            ParsedPaper 또는 None
        """
        async with AsyncEuropePMCClient(
            max_concurrent=1,
            delay=self.config.api.delay,
            timeout=self.config.api.timeout,
        ) as client:
            xml = await client.get_fulltext_xml(pmcid)

        if not xml:
            return None

        parsed = self.parser.parse(xml)

        if save_to_db:
            async with self.db.connect():
                await self.db.save_all(parsed)

        if save_to_s3:
            self.s3.save_all(parsed)

        return parsed


def run_pipeline_sync(
    query: str,
    limit: int = 10,
    max_concurrent: int = 10,
    save_to_db: bool = True,
    save_to_s3: bool = True,
) -> PipelineResult:
    """동기 방식 파이프라인 실행 (편의 함수)"""
    pipeline = Pipeline()
    return asyncio.run(
        pipeline.run(
            query=query,
            limit=limit,
            max_concurrent=max_concurrent,
            save_to_db=save_to_db,
            save_to_s3=save_to_s3,
        )
    )
