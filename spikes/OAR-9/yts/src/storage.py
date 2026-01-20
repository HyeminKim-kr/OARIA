"""
저장소 모듈

PostgreSQL (asyncpg) 및 S3 (boto3/MinIO) 저장 로직
기반: OAR-19/yts/src/storage.py
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
        """논문 저장 (papers 테이블)"""
        query = """
            INSERT INTO papers (
                paper_id, pmcid, pmid, doi,
                title, abstract, journal, year,
                keywords, source, source_url, is_open_access,
                canonical_prefix, canonical_text_version,
                canonical_text_hash, canonical_text_length,
                raw_xml_hash, parser_version
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8,
                $9, $10, $11, $12,
                $13, $14, $15, $16,
                $17, $18
            )
            ON CONFLICT (paper_id) DO UPDATE SET
                title = EXCLUDED.title,
                abstract = EXCLUDED.abstract,
                journal = EXCLUDED.journal,
                year = EXCLUDED.year,
                keywords = EXCLUDED.keywords,
                source_url = EXCLUDED.source_url,
                canonical_text_hash = EXCLUDED.canonical_text_hash,
                canonical_text_length = EXCLUDED.canonical_text_length,
                raw_xml_hash = EXCLUDED.raw_xml_hash,
                parser_version = EXCLUDED.parser_version,
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
                db_dict["source_url"],
                db_dict["is_open_access"],
                db_dict["canonical_prefix"],
                db_dict["canonical_text_version"],
                db_dict["canonical_text_hash"],
                db_dict["canonical_text_length"],
                db_dict["raw_xml_hash"],
                db_dict["parser_version"],
            )
            return result

    async def save_authors(self, paper: ParsedPaper, db_id: str) -> int:
        """저자 저장 (paper_authors 테이블)"""
        if not paper.authors:
            return 0

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
        """섹션 저장 (paper_sections 테이블)"""
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
                        section.name[:50],
                        section.title[:500] if section.title else None,
                        section.offset_start,
                        section.offset_end,
                    )
        return len(paper.sections)

    async def save_all(self, paper: ParsedPaper) -> dict:
        """논문 전체 저장 (트랜잭션)"""
        db_id = await self.save_paper(paper)
        authors_count = await self.save_authors(paper, db_id)
        sections_count = await self.save_sections(paper, db_id)

        return {
            "paper_id": paper.paper_id,
            "db_id": str(db_id),
            "authors_count": authors_count,
            "sections_count": sections_count,
        }

    async def get_papers(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """논문 목록 조회"""
        query = """
            SELECT
                id, paper_id, pmcid, pmid, doi,
                title, journal, year, source, source_url,
                canonical_prefix, canonical_text_version,
                canonical_text_hash, canonical_text_length,
                raw_xml_hash, parser_version,
                created_at, updated_at
            FROM papers
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            return [dict(row) for row in rows]

    async def get_paper_by_id(self, paper_id: str) -> dict | None:
        """paper_id로 논문 조회"""
        query = """
            SELECT *
            FROM papers
            WHERE paper_id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, paper_id)
            return dict(row) if row else None

    async def get_papers_count(self) -> int:
        """전체 논문 수 조회"""
        query = "SELECT COUNT(*) FROM papers"
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query)


class S3Storage:
    """S3/MinIO 저장소"""

    def __init__(self, config: Config):
        self.config = config
        self._client = None

    def _get_client(self):
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
        except Exception:
            client.create_bucket(Bucket=self.config.s3.bucket)

    def save_canonical_text(self, paper: ParsedPaper, version: str = "v1") -> str:
        """canonical_text S3 저장"""
        client = self._get_client()
        key = f"{paper.canonical_prefix}{version}.txt"

        client.put_object(
            Bucket=self.config.s3.bucket,
            Key=key,
            Body=paper.canonical_text.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
            Metadata={
                "paper_id": paper.paper_id,
                "hash": paper.canonical_text_hash,
                "version": version,
            },
        )
        return key

    def save_versions_metadata(self, paper: ParsedPaper, version: str = "v1") -> str:
        """버전 이력 메타데이터 S3 저장"""
        from datetime import datetime, timezone

        client = self._get_client()
        key = f"{paper.canonical_prefix}versions.json"

        existing_versions = {}
        try:
            response = client.get_object(Bucket=self.config.s3.bucket, Key=key)
            existing_versions = json.loads(response['Body'].read().decode('utf-8'))
        except Exception:
            pass

        versions_data = existing_versions.get("versions", {})
        versions_data[version] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hash": paper.canonical_text_hash,
            "length": paper.canonical_text_length,
            "source": paper.source,
            "sections": [s.name for s in paper.sections],
        }

        metadata = {
            "paper_id": paper.paper_id,
            "current_version": version,
            "versions": versions_data,
        }

        client.put_object(
            Bucket=self.config.s3.bucket,
            Key=key,
            Body=json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        return key

    def save_all(self, paper: ParsedPaper, version: str = "v1") -> dict:
        """논문 전체 S3 저장"""
        self.ensure_bucket()
        text_key = self.save_canonical_text(paper, version=version)
        versions_key = self.save_versions_metadata(paper, version=version)

        return {
            "text_key": text_key,
            "metadata_key": versions_key,
        }

    def get_canonical_text(self, canonical_prefix: str, version: str = "v1") -> str | None:
        """S3에서 canonical_text 조회"""
        client = self._get_client()
        key = f"{canonical_prefix}{version}.txt"

        try:
            response = client.get_object(Bucket=self.config.s3.bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except Exception:
            return None

    def get_text_by_paper_id(self, paper_id: str, version: str = "v1") -> str | None:
        """paper_id로 canonical_text 조회"""
        safe_id = paper_id.replace(":", "_").replace("/", "_")
        canonical_prefix = f"canonical/{safe_id}/"
        return self.get_canonical_text(canonical_prefix, version)
