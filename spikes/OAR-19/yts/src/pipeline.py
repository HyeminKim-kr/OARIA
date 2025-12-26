"""
파이프라인 모듈

수집 → 파싱 → 저장 전체 흐름 관리
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from .europe_pmc_client import EuropePMCClient, PaperInfo
from .parser import parse_fulltext_xml
from .models import ParsedPaper
from .storage import DatabaseStorage, S3Storage
from .config import Config


@dataclass
class PipelineStep:
    """파이프라인 단계 상태"""
    name: str
    status: str = "pending"  # pending, running, success, error
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: str = ""
    data: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> Optional[int]:
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds() * 1000)
        return None


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""
    query: str
    pmcid: str
    steps: list[PipelineStep] = field(default_factory=list)
    paper: Optional[ParsedPaper] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return all(s.status == "success" for s in self.steps)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "pmcid": self.pmcid,
            "success": self.success,
            "error": self.error,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "message": s.message,
                    "data": s.data,
                }
                for s in self.steps
            ],
            "paper": {
                "paper_id": self.paper.paper_id,
                "title": self.paper.title,
                "year": self.paper.year,
                "authors_count": len(self.paper.authors),
                "sections_count": len(self.paper.sections),
                "canonical_text_length": self.paper.canonical_text_length,
            } if self.paper else None,
        }


class Pipeline:
    """수집 → 파싱 → 저장 파이프라인"""

    def __init__(
        self,
        config: Optional[Config] = None,
        on_step: Optional[Callable[[PipelineStep], None]] = None,
    ):
        """
        Args:
            config: 설정 (DB, S3)
            on_step: 단계별 콜백 (UI 업데이트용)
        """
        self.config = config or Config.from_env()
        self.on_step = on_step or (lambda s: None)
        self.client = EuropePMCClient()

    def _update_step(self, step: PipelineStep, status: str, message: str = "", **data):
        """단계 상태 업데이트 및 콜백 호출"""
        step.status = status
        step.message = message
        step.data.update(data)

        if status == "running":
            step.started_at = datetime.now()
        elif status in ("success", "error"):
            step.finished_at = datetime.now()

        self.on_step(step)

    def run_search(self, query: str, limit: int = 5) -> list[PaperInfo]:
        """1단계: 검색"""
        return self.client.search(query, limit=limit, open_access_only=True)

    def run_single(
        self,
        query: str,
        pmcid: str,
        save_to_db: bool = False,
        save_to_s3: bool = False,
        paper_info: Optional[PaperInfo] = None,
    ) -> PipelineResult:
        """단일 논문 파이프라인 실행

        Args:
            query: 원본 검색 쿼리 (로깅용)
            pmcid: 처리할 PMC ID
            save_to_db: DB 저장 여부
            save_to_s3: S3 저장 여부
            paper_info: Search API에서 받은 메타데이터 (PMID 등 병합용)
        """
        result = PipelineResult(query=query, pmcid=pmcid)

        # Step 1: XML 수집
        step1 = PipelineStep(name="collect")
        result.steps.append(step1)
        self._update_step(step1, "running", "Europe PMC에서 XML 수집 중...")

        try:
            xml_content = self.client.get_fulltext_xml(pmcid)
            if not xml_content:
                self._update_step(step1, "error", "XML 수집 실패")
                result.error = "XML 수집 실패"
                return result

            self._update_step(
                step1, "success",
                f"XML 수집 완료 ({len(xml_content):,} bytes)",
                xml_size=len(xml_content),
            )
        except Exception as e:
            self._update_step(step1, "error", str(e))
            result.error = str(e)
            return result

        # Step 2: 파싱
        step2 = PipelineStep(name="parse")
        result.steps.append(step2)
        self._update_step(step2, "running", "XML 파싱 중...")

        try:
            paper = parse_fulltext_xml(xml_content)

            # Search API 메타데이터 병합 (XML에 없는 필드 보완)
            if paper_info:
                if not paper.pmid and paper_info.pmid:
                    paper.pmid = paper_info.pmid
                if not paper.doi and paper_info.doi:
                    paper.doi = paper_info.doi
                if not paper.journal and paper_info.journal:
                    paper.journal = paper_info.journal
                if not paper.year and paper_info.year:
                    paper.year = paper_info.year

            result.paper = paper

            self._update_step(
                step2, "success",
                f"파싱 완료: 저자 {len(paper.authors)}명, 섹션 {len(paper.sections)}개",
                authors_count=len(paper.authors),
                sections_count=len(paper.sections),
                canonical_length=paper.canonical_text_length,
            )
        except Exception as e:
            self._update_step(step2, "error", str(e))
            result.error = str(e)
            return result

        # Step 3: S3 저장 (선택)
        if save_to_s3:
            step3 = PipelineStep(name="s3_save")
            result.steps.append(step3)
            self._update_step(step3, "running", "S3에 저장 중...")

            try:
                s3_storage = S3Storage(self.config)
                s3_result = s3_storage.save_all(paper)

                self._update_step(
                    step3, "success",
                    f"S3 저장 완료",
                    text_key=s3_result["text_key"],
                    metadata_key=s3_result["metadata_key"],
                )
            except Exception as e:
                self._update_step(step3, "error", str(e))
                # S3 실패는 치명적이지 않음, 계속 진행

        # Step 4: DB 저장 (선택)
        if save_to_db:
            step4 = PipelineStep(name="db_save")
            result.steps.append(step4)
            self._update_step(step4, "running", "PostgreSQL에 저장 중...")

            # DB 저장은 async이므로 여기서는 준비만
            step4.data["pending"] = True
            self._update_step(step4, "pending", "DB 저장 대기 중 (async 필요)")

        return result

    async def run_single_async(
        self,
        query: str,
        pmcid: str,
        save_to_db: bool = True,
        save_to_s3: bool = True,
        paper_info: Optional[PaperInfo] = None,
    ) -> PipelineResult:
        """단일 논문 파이프라인 실행 (async, DB 저장 포함)"""
        # 동기 부분 먼저 실행
        result = self.run_single(
            query=query,
            pmcid=pmcid,
            save_to_db=False,  # 나중에 async로
            save_to_s3=save_to_s3,
            paper_info=paper_info,  # Search API 메타데이터 전달
        )

        if not result.paper:
            return result

        # DB 저장 (async)
        if save_to_db:
            step = PipelineStep(name="db_save")
            result.steps.append(step)
            self._update_step(step, "running", "PostgreSQL에 저장 중...")

            try:
                db_storage = DatabaseStorage(self.config)
                async with db_storage.connect():
                    db_result = await db_storage.save_all(result.paper)

                self._update_step(
                    step, "success",
                    f"DB 저장 완료",
                    paper_id=db_result["paper_id"],
                    authors_saved=db_result["authors_count"],
                    sections_saved=db_result["sections_count"],
                )
            except Exception as e:
                self._update_step(step, "error", str(e))

        return result

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
