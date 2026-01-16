"""PostgreSQL 저장소

OAR-19 스타일: Connection Pool 사용
"""

import hashlib
from dataclasses import dataclass, field
from contextlib import contextmanager

from psycopg_pool import ConnectionPool
import structlog

from ..config import settings
from ..models import Paper

logger = structlog.get_logger()

# 모듈 레벨 싱글톤 Pool
_storage_pool: ConnectionPool | None = None


def get_storage_pool() -> ConnectionPool:
    """Storage용 Connection Pool 획득"""
    global _storage_pool
    if _storage_pool is None:
        _storage_pool = ConnectionPool(
            conninfo=settings.db.dsn,
            min_size=2,
            max_size=40,
            open=True,
        )
        logger.info("storage_pool_created", min_size=2, max_size=40)
    return _storage_pool


@dataclass
class DatabaseStorage:
    """PostgreSQL 저장소 (Connection Pool 사용)"""

    _pool: ConnectionPool | None = field(default=None, repr=False)

    def connect(self) -> None:
        """Pool 연결"""
        self._pool = get_storage_pool()

    def close(self) -> None:
        """Pool은 공유되므로 여기서 닫지 않음"""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @contextmanager
    def _get_connection(self):
        """Pool에서 연결 획득"""
        with self._pool.connection() as conn:
            yield conn

    def save_paper(self, paper: Paper, s3_prefix: str | None = None) -> str:
        """논문 저장 (upsert)

        OAR-19 스타일: Pool에서 연결 획득하여 사용

        Args:
            paper: 논문 데이터
            s3_prefix: S3 저장 경로 (canonical_prefix)

        Returns:
            paper의 UUID
        """
        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    # 1. papers 테이블 upsert
                    cur.execute(
                        """
                        INSERT INTO papers (
                            paper_id, pmcid, pmid, doi,
                            title, abstract, journal, year, keywords,
                            canonical_prefix, canonical_text_hash, canonical_text_length,
                            raw_xml_hash, source, source_url, is_open_access,
                            status, created_at, updated_at
                        ) VALUES (
                            %(paper_id)s, %(pmcid)s, %(pmid)s, %(doi)s,
                            %(title)s, %(abstract)s, %(journal)s, %(year)s, %(keywords)s,
                            %(canonical_prefix)s, %(text_hash)s, %(text_length)s,
                            %(raw_xml_hash)s, %(source)s, %(source_url)s, %(is_open_access)s,
                            'collected', NOW(), NOW()
                        )
                        ON CONFLICT (paper_id) DO UPDATE SET
                            pmcid = EXCLUDED.pmcid,
                            pmid = EXCLUDED.pmid,
                            doi = EXCLUDED.doi,
                            title = EXCLUDED.title,
                            abstract = EXCLUDED.abstract,
                            journal = EXCLUDED.journal,
                            year = EXCLUDED.year,
                            keywords = EXCLUDED.keywords,
                            canonical_prefix = EXCLUDED.canonical_prefix,
                            canonical_text_hash = EXCLUDED.canonical_text_hash,
                            canonical_text_length = EXCLUDED.canonical_text_length,
                            raw_xml_hash = EXCLUDED.raw_xml_hash,
                            updated_at = NOW()
                        RETURNING id
                        """,
                        {
                            "paper_id": paper.paper_id,
                            "pmcid": paper.pmcid,
                            "pmid": paper.pmid,
                            "doi": paper.doi,
                            "title": paper.title,
                            "abstract": paper.abstract,
                            "journal": paper.journal,
                            "year": paper.year,
                            "keywords": paper.keywords or [],
                            "canonical_prefix": s3_prefix,
                            "text_hash": self._compute_text_hash(paper.fulltext),
                            "text_length": len(paper.fulltext) if paper.fulltext else 0,
                            "raw_xml_hash": paper.raw_xml_hash,
                            "source": paper.source,
                            "source_url": paper.source_url,
                            "is_open_access": paper.is_open_access,
                        },
                    )

                    paper_uuid = cur.fetchone()[0]

                    # 2. paper_authors 저장
                    if paper.authors:
                        cur.execute(
                            "DELETE FROM paper_authors WHERE paper_id = %s", (paper_uuid,)
                        )

                        for author in paper.authors:
                            cur.execute(
                                """
                                INSERT INTO paper_authors (
                                    paper_id, author_order, author_name,
                                    is_corresponding, orcid, affiliation
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    paper_uuid,
                                    author.order,
                                    author.name,
                                    author.is_corresponding,
                                    author.orcid,
                                    author.affiliation,
                                ),
                            )

                    # 3. paper_sections 저장
                    if paper.sections:
                        cur.execute(
                            "DELETE FROM paper_sections WHERE paper_id = %s", (paper_uuid,)
                        )

                        for section in paper.sections:
                            cur.execute(
                                """
                                INSERT INTO paper_sections (
                                    paper_id, section_order, section_name, section_title,
                                    offset_start, offset_end
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    paper_uuid,
                                    section.order,
                                    section.name,
                                    section.title,
                                    section.offset_start,
                                    section.offset_end,
                                ),
                            )

                    # 트랜잭션 커밋
                    conn.commit()

                    logger.info(
                        "paper_saved",
                        paper_id=paper.paper_id,
                        pmcid=paper.pmcid,
                        pmid=paper.pmid,
                        doi=paper.doi,
                        uuid=str(paper_uuid),
                        authors=len(paper.authors) if paper.authors else 0,
                        sections=len(paper.sections) if paper.sections else 0,
                    )

                    return str(paper_uuid)

            except Exception as e:
                conn.rollback()
                logger.error(
                    "paper_save_failed",
                    paper_id=paper.paper_id,
                    error=str(e),
                )
                raise

    def paper_exists(self, paper_id: str) -> bool:
        """논문 존재 여부 확인"""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM papers WHERE paper_id = %s",
                    (paper_id,),
                )
                return cur.fetchone() is not None

    def get_paper_count(self) -> int:
        """저장된 논문 수"""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM papers")
                return cur.fetchone()[0]

    def _compute_text_hash(self, text: str | None) -> str | None:
        """텍스트 해시 계산"""
        if not text:
            return None
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ============================================================
    # 논문 관계 처리 (paper_relations, flags)
    # ============================================================

    def update_paper_pub_types(self, pmid: str, pub_types: list[str]) -> None:
        """논문의 pub_types 업데이트

        Args:
            pmid: 논문 PMID
            pub_types: pubType 배열
        """
        if not pmid or not pub_types:
            return

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE papers
                    SET pub_types = %s, updated_at = NOW()
                    WHERE pmid = %s
                    """,
                    (pub_types, pmid),
                )
                conn.commit()

    def save_paper_relation(
        self,
        source_pmid: str,
        target_pmid: str,
        relation_type: str,
        raw_type: str | None = None,
        reference: str | None = None,
    ) -> bool:
        """논문 관계 저장 (UPSERT)

        Args:
            source_pmid: 관계 출처 논문 PMID (Correction/Retraction 문서)
            target_pmid: 대상 논문 PMID (원문)
            relation_type: 정규화된 관계 타입 (retraction, erratum, correction, comment)
            raw_type: 원본 관계 문자열
            reference: 참조 문자열

        Returns:
            bool: 성공 여부
        """
        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO paper_relations (
                            source_pmid, target_pmid, relation_type,
                            raw_type, reference
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (source_pmid, target_pmid, relation_type)
                        DO UPDATE SET
                            raw_type = EXCLUDED.raw_type,
                            reference = EXCLUDED.reference
                        """,
                        (source_pmid, target_pmid, relation_type, raw_type, reference),
                    )
                    conn.commit()

                logger.debug(
                    "relation_saved",
                    source_pmid=source_pmid,
                    target_pmid=target_pmid,
                    relation_type=relation_type,
                )
                return True

            except Exception as e:
                conn.rollback()
                logger.error(
                    "relation_save_failed",
                    source_pmid=source_pmid,
                    target_pmid=target_pmid,
                    relation_type=relation_type,
                    error=str(e),
                )
                return False

    def update_paper_flag(
        self,
        pmid: str,
        flag_column: str,
        value: bool = True,
    ) -> bool:
        """논문 플래그 업데이트 (UPSERT 방식)

        원문이 아직 수집되지 않았어도 플래그를 설정할 수 있도록
        해당 pmid의 레코드가 없으면 무시

        Args:
            pmid: 대상 논문 PMID
            flag_column: 플래그 컬럼명 (has_retraction, has_erratum, has_correction)
            value: 플래그 값 (기본 True)

        Returns:
            bool: 업데이트 성공 여부
        """
        if flag_column not in ("has_retraction", "has_erratum", "has_correction"):
            logger.warning("invalid_flag_column", flag_column=flag_column)
            return False

        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    # 동적 SQL 구성 (안전한 컬럼명)
                    sql = f"""
                        UPDATE papers
                        SET {flag_column} = %s, updated_at = NOW()
                        WHERE pmid = %s
                    """
                    cur.execute(sql, (value, pmid))
                    updated = cur.rowcount > 0
                    conn.commit()

                if updated:
                    logger.debug(
                        "flag_updated",
                        pmid=pmid,
                        flag_column=flag_column,
                        value=value,
                    )
                else:
                    logger.debug(
                        "flag_update_skipped_no_paper",
                        pmid=pmid,
                        flag_column=flag_column,
                    )

                return updated

            except Exception as e:
                conn.rollback()
                logger.error(
                    "flag_update_failed",
                    pmid=pmid,
                    flag_column=flag_column,
                    error=str(e),
                )
                return False

    def process_paper_relations(
        self,
        current_pmid: str,
        relations: list,  # list[ParsedRelation]
    ) -> dict:
        """논문 관계 일괄 처리

        Args:
            current_pmid: 현재 논문 PMID
            relations: ParsedRelation 리스트

        Returns:
            dict: 처리 통계 {saved: int, flagged: int}
        """
        from ..collectors.pub_type_filter import (
            RelationDirection,
            RelationType,
            get_flag_column,
        )

        stats = {"saved": 0, "flagged": 0}

        for rel in relations:
            # 1. 관계 저장
            # 방향에 따라 source/target 결정
            if rel.direction == RelationDirection.OUTWARD:
                # 현재 문서가 Correction, target이 원문
                source = current_pmid
                target = rel.target_pmid
            else:
                # 현재 문서가 원문, target이 Correction
                source = rel.target_pmid
                target = current_pmid

            saved = self.save_paper_relation(
                source_pmid=source,
                target_pmid=target,
                relation_type=rel.relation_type.value,
                raw_type=rel.raw_type,
                reference=rel.reference,
            )
            if saved:
                stats["saved"] += 1

            # 2. 플래그 업데이트 (comment 제외)
            flag_column = get_flag_column(rel.relation_type)
            if flag_column:
                # 원문에 플래그 설정
                if rel.direction == RelationDirection.OUTWARD:
                    # 현재 문서가 Correction → target(원문)에 플래그
                    flagged = self.update_paper_flag(rel.target_pmid, flag_column)
                else:
                    # 현재 문서가 원문 → 현재 문서에 플래그
                    flagged = self.update_paper_flag(current_pmid, flag_column)

                if flagged:
                    stats["flagged"] += 1

        if stats["saved"] > 0 or stats["flagged"] > 0:
            logger.info(
                "relations_processed",
                current_pmid=current_pmid,
                **stats,
            )

        return stats

    # ============================================================
    # PDF 관련 메서드
    # ============================================================

    def update_paper_pdf_info(
        self,
        paper_id: str,
        pdf_size: int,
        pdf_hash: str,
    ) -> bool:
        """PDF 정보 업데이트

        Args:
            paper_id: 논문 paper_id (예: "pmc:PMC12345678")
            pdf_size: PDF 파일 크기 (bytes)
            pdf_hash: PDF SHA256 해시

        Returns:
            bool: 업데이트 성공 여부
        """
        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE papers SET
                            has_pdf = true,
                            pdf_size = %s,
                            pdf_hash = %s,
                            pdf_downloaded_at = NOW(),
                            updated_at = NOW()
                        WHERE paper_id = %s
                        """,
                        (pdf_size, pdf_hash, paper_id),
                    )
                    updated = cur.rowcount > 0
                    conn.commit()

                if updated:
                    logger.info(
                        "pdf_info_updated",
                        paper_id=paper_id,
                        pdf_size=pdf_size,
                    )

                return updated

            except Exception as e:
                conn.rollback()
                logger.error(
                    "pdf_info_update_failed",
                    paper_id=paper_id,
                    error=str(e),
                )
                return False

    # ============================================================
    # Citations 관련 메서드
    # ============================================================

    def save_citation(
        self,
        source_paper_id: str,
        target_paper_id: str,
        source_pmcid: str | None = None,
        source_pmid: str | None = None,
        target_pmcid: str | None = None,
        target_pmid: str | None = None,
        collected_from: str = "",
    ) -> bool:
        """인용 관계 저장 (UPSERT)

        Args:
            source_paper_id: 인용하는 논문 (citing paper)
            target_paper_id: 인용되는 논문 (cited paper)
            source_pmcid: Source PMCID
            source_pmid: Source PMID
            target_pmcid: Target PMCID
            target_pmid: Target PMID
            collected_from: 어떤 논문 수집 시 발견됨

        Returns:
            bool: 성공 여부
        """
        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO paper_citations (
                            source_paper_id, target_paper_id,
                            source_pmcid, source_pmid,
                            target_pmcid, target_pmid,
                            collected_from
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_paper_id, target_paper_id) DO NOTHING
                        """,
                        (
                            source_paper_id,
                            target_paper_id,
                            source_pmcid,
                            source_pmid,
                            target_pmcid,
                            target_pmid,
                            collected_from,
                        ),
                    )
                    conn.commit()
                    return True

            except Exception as e:
                conn.rollback()
                logger.error(
                    "citation_save_failed",
                    source_paper_id=source_paper_id,
                    target_paper_id=target_paper_id,
                    error=str(e),
                )
                return False

    def update_citation_counts(self, paper_id: str) -> bool:
        """인용/참조 카운트 업데이트

        Args:
            paper_id: 논문 paper_id

        Returns:
            bool: 업데이트 성공 여부
        """
        with self._pool.connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE papers SET
                            citation_count = (
                                SELECT COUNT(*) FROM paper_citations
                                WHERE target_paper_id = papers.paper_id
                            ),
                            reference_count = (
                                SELECT COUNT(*) FROM paper_citations
                                WHERE source_paper_id = papers.paper_id
                            ),
                            updated_at = NOW()
                        WHERE paper_id = %s
                        """,
                        (paper_id,),
                    )
                    conn.commit()
                    return True

            except Exception as e:
                conn.rollback()
                logger.error(
                    "citation_count_update_failed",
                    paper_id=paper_id,
                    error=str(e),
                )
                return False

    def get_citation_stats(self, paper_id: str) -> dict:
        """인용 통계 조회

        Args:
            paper_id: 논문 paper_id

        Returns:
            dict: {citation_count, reference_count}
        """
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT citation_count, reference_count
                    FROM papers WHERE paper_id = %s
                    """,
                    (paper_id,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "citation_count": row[0] or 0,
                        "reference_count": row[1] or 0,
                    }
                return {"citation_count": 0, "reference_count": 0}
