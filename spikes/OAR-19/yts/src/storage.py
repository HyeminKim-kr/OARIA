"""
저장소 모듈

PostgreSQL (asyncpg) 및 S3 (boto3) 저장 로직
"""

import json
from contextlib import asynccontextmanager

import asyncpg
import boto3
from botocore.client import Config as BotoConfig

from .config import Config
from .models import ParsedPaper


class DatabaseStorage:
    """PostgreSQL 저장소 (asyncpg)"""

    def __init__(self, config: Config):
        self.config = config
        self._pool: asyncpg.Pool | None = None

    @asynccontextmanager
    async def connect(self):
        """연결 풀 컨텍스트 매니저"""
        self._pool = await asyncpg.create_pool(
            dsn=self.config.db.dsn,
            min_size=2,
            max_size=10,
        )
        try:
            yield self
        finally:
            await self._pool.close()

    async def save_paper(self, paper: ParsedPaper) -> str:
        """논문 저장 (papers 테이블)

        Returns:
            저장된 UUID (id)
        """
        query = """
            INSERT INTO papers (
                paper_id, pmcid, pmid, doi,
                title, abstract, journal, year,
                keywords, source, is_open_access,
                canonical_prefix, canonical_text_version,
                canonical_text_hash, canonical_text_length
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8,
                $9, $10, $11,
                $12, $13, $14, $15
            )
            ON CONFLICT (paper_id) DO UPDATE SET
                title = EXCLUDED.title,
                abstract = EXCLUDED.abstract,
                journal = EXCLUDED.journal,
                year = EXCLUDED.year,
                keywords = EXCLUDED.keywords,
                canonical_text_hash = EXCLUDED.canonical_text_hash,
                canonical_text_length = EXCLUDED.canonical_text_length,
                updated_at = NOW()
            RETURNING id
        """
        db_dict = paper.to_db_dict()

        async with self._pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                db_dict["paper_id"],
                db_dict["pmcid"],
                db_dict["pmid"],
                db_dict["doi"],
                db_dict["title"],
                db_dict["abstract"],
                db_dict["journal"],
                db_dict["year"],
                db_dict["keywords"],
                db_dict["source"],
                db_dict["is_open_access"],
                db_dict["canonical_prefix"],
                db_dict["canonical_text_version"],
                db_dict["canonical_text_hash"],
                db_dict["canonical_text_length"],
            )
            return result

    async def save_authors(self, paper: ParsedPaper, db_id: str) -> int:
        """저자 저장 (paper_authors 테이블)

        Args:
            paper: ParsedPaper 객체
            db_id: papers 테이블의 UUID (id)

        Returns:
            저장된 저자 수
        """
        if not paper.authors:
            return 0

        # 기존 저자 삭제 (업데이트 시)
        delete_query = "DELETE FROM paper_authors WHERE paper_id = $1"

        insert_query = """
            INSERT INTO paper_authors (
                paper_id, author_order, author_name,
                orcid, affiliation, is_corresponding
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(delete_query, db_id)

                for author in paper.authors:
                    await conn.execute(
                        insert_query,
                        db_id,
                        author.order,
                        author.name,
                        author.orcid,
                        author.affiliation,
                        author.is_corresponding,
                    )

        return len(paper.authors)

    async def save_sections(self, paper: ParsedPaper, db_id: str) -> int:
        """섹션 저장 (paper_sections 테이블)

        Args:
            paper: ParsedPaper 객체
            db_id: papers 테이블의 UUID (id)

        Returns:
            저장된 섹션 수
        """
        if not paper.sections:
            return 0

        delete_query = "DELETE FROM paper_sections WHERE paper_id = $1"

        insert_query = """
            INSERT INTO paper_sections (
                paper_id, section_order, section_name, section_title,
                offset_start, offset_end
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(delete_query, db_id)

                for section in paper.sections:
                    await conn.execute(
                        insert_query,
                        db_id,
                        section.order,
                        section.name[:50],  # VARCHAR(50) 제한
                        section.title[:500] if section.title else None,  # 안전하게 truncate
                        section.offset_start,
                        section.offset_end,
                    )

        return len(paper.sections)

    async def save_all(self, paper: ParsedPaper) -> dict:
        """논문 전체 저장 (트랜잭션)

        Returns:
            저장 결과 {paper_id, db_id, authors_count, sections_count}
        """
        db_id = await self.save_paper(paper)
        authors_count = await self.save_authors(paper, db_id)
        sections_count = await self.save_sections(paper, db_id)

        return {
            "paper_id": paper.paper_id,
            "db_id": str(db_id),
            "authors_count": authors_count,
            "sections_count": sections_count,
        }


class S3Storage:
    """S3 저장소 (boto3, MinIO 호환)"""

    def __init__(self, config: Config):
        self.config = config
        self._client = None

    def _get_client(self):
        """S3 클라이언트 생성 (지연 초기화)"""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.config.s3.endpoint_url,
                aws_access_key_id=self.config.s3.access_key,
                aws_secret_access_key=self.config.s3.secret_key,
                config=BotoConfig(signature_version="s3v4"),
            )
        return self._client

    def ensure_bucket(self):
        """버킷 존재 확인 및 생성"""
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.config.s3.bucket)
        except client.exceptions.ClientError:
            client.create_bucket(Bucket=self.config.s3.bucket)

    def save_canonical_text(self, paper: ParsedPaper) -> str:
        """canonical_text S3 저장

        저장 경로: canonical/{paper_id}/text.txt

        Returns:
            S3 키
        """
        client = self._get_client()
        key = f"{paper.canonical_prefix}text.txt"

        client.put_object(
            Bucket=self.config.s3.bucket,
            Key=key,
            Body=paper.canonical_text.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
            Metadata={
                "paper_id": paper.paper_id,
                "hash": paper.canonical_text_hash,
                "version": "v1",
            },
        )

        return key

    def save_metadata(self, paper: ParsedPaper) -> str:
        """메타데이터 JSON S3 저장

        저장 경로: canonical/{paper_id}/metadata.json

        Returns:
            S3 키
        """
        client = self._get_client()
        key = f"{paper.canonical_prefix}metadata.json"

        metadata = {
            "paper_id": paper.paper_id,
            "pmcid": paper.pmcid,
            "pmid": paper.pmid,
            "doi": paper.doi,
            "title": paper.title,
            "year": paper.year,
            "journal": paper.journal,
            "keywords": paper.keywords,
            "mesh_terms": paper.mesh_terms,
            "authors": [
                {
                    "name": a.name,
                    "order": a.order,
                    "orcid": a.orcid,
                    "affiliation": a.affiliation,
                    "is_corresponding": a.is_corresponding,
                }
                for a in paper.authors
            ],
            "sections": [
                {
                    "name": s.name,
                    "title": s.title,
                    "order": s.order,
                    "offset_start": s.offset_start,
                    "offset_end": s.offset_end,
                    "char_count": s.char_count,
                }
                for s in paper.sections
            ],
            "canonical_text_hash": paper.canonical_text_hash,
            "canonical_text_length": paper.canonical_text_length,
        }

        client.put_object(
            Bucket=self.config.s3.bucket,
            Key=key,
            Body=json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )

        return key

    def save_all(self, paper: ParsedPaper) -> dict:
        """논문 전체 S3 저장

        Returns:
            저장된 키 목록 {text_key, metadata_key}
        """
        self.ensure_bucket()

        text_key = self.save_canonical_text(paper)
        metadata_key = self.save_metadata(paper)

        return {
            "text_key": text_key,
            "metadata_key": metadata_key,
        }
