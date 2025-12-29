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
