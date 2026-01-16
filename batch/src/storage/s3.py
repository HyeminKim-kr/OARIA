"""S3/MinIO 저장소

논문 원문(XML, fulltext, display, PDF) 저장
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field

import boto3
import structlog
from botocore.exceptions import ClientError

from ..config import settings
from ..models import Paper

logger = structlog.get_logger()


@dataclass
class S3Storage:
    """S3/MinIO 저장소"""

    endpoint_url: str = field(default_factory=lambda: settings.s3.endpoint_url)
    access_key: str = field(default_factory=lambda: settings.s3.access_key)
    secret_key: str = field(default_factory=lambda: settings.s3.secret_key)
    bucket: str = field(default_factory=lambda: settings.s3.bucket)

    _client: boto3.client = field(default=None, repr=False)

    def __post_init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def save_paper(self, paper: Paper) -> str:
        """논문 저장

        Args:
            paper: 논문 데이터

        Returns:
            S3 prefix (canonical_prefix)
        """
        # prefix 생성: canonical/{paper_id}/
        # paper_id: pmc:PMC12345678 → pmc_PMC12345678
        safe_id = paper.paper_id.replace(":", "_")
        prefix = f"canonical/{safe_id}"

        # 1. raw XML 저장
        if paper.raw_xml:
            self._put_object(
                key=f"{prefix}/raw.xml",
                body=paper.raw_xml,
                content_type="application/xml",
            )

        # 2. fulltext 저장
        if paper.fulltext:
            self._put_object(
                key=f"{prefix}/fulltext.txt",
                body=paper.fulltext,
                content_type="text/plain; charset=utf-8",
            )

        # 3. display.json 저장 (가독성용 섹션/문단 구조 + Figure 정보)
        if paper.display_sections:
            display_data = {
                "sections": [asdict(sec) for sec in paper.display_sections],
                "figures": [asdict(fig) for fig in paper.figures] if paper.figures else [],
            }
            self._put_object(
                key=f"{prefix}/display.json",
                body=json.dumps(display_data, ensure_ascii=False, indent=2),
                content_type="application/json; charset=utf-8",
            )

        logger.info(
            "paper_saved_s3",
            paper_id=paper.paper_id,
            prefix=prefix,
            has_xml=paper.raw_xml is not None,
            has_fulltext=paper.fulltext is not None,
            has_display=bool(paper.display_sections),
            figure_count=len(paper.figures) if paper.figures else 0,
        )

        return prefix

    def _put_object(self, key: str, body: str, content_type: str) -> None:
        """S3 객체 저장"""
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType=content_type,
        )

    def get_fulltext(self, prefix: str) -> str | None:
        """fulltext 조회"""
        try:
            response = self._client.get_object(
                Bucket=self.bucket,
                Key=f"{prefix}/fulltext.txt",
            )
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def get_raw_xml(self, prefix: str) -> str | None:
        """raw XML 조회"""
        try:
            response = self._client.get_object(
                Bucket=self.bucket,
                Key=f"{prefix}/raw.xml",
            )
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def get_display(self, prefix: str) -> dict | None:
        """display.json 조회 (가독성용 섹션/문단 구조)"""
        try:
            response = self._client.get_object(
                Bucket=self.bucket,
                Key=f"{prefix}/display.json",
            )
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def exists(self, prefix: str) -> bool:
        """prefix 존재 여부"""
        try:
            self._client.head_object(
                Bucket=self.bucket,
                Key=f"{prefix}/fulltext.txt",
            )
            return True
        except ClientError:
            return False

    def save_pdf(self, paper_id: str, pdf_bytes: bytes) -> tuple[str, int, str]:
        """PDF 저장

        Args:
            paper_id: 논문 ID (예: "pmc:PMC12345678")
            pdf_bytes: PDF 바이트 데이터

        Returns:
            (s3_key, size, sha256_hash)
        """
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/paper.pdf"

        # SHA256 해시 계산
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        size = len(pdf_bytes)

        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )

        logger.info(
            "pdf_saved_s3",
            paper_id=paper_id,
            key=key,
            size=size,
        )

        return key, size, pdf_hash

    def get_pdf(self, prefix: str) -> bytes | None:
        """PDF 조회"""
        try:
            response = self._client.get_object(
                Bucket=self.bucket,
                Key=f"{prefix}/paper.pdf",
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def get_pdf_presigned_url(self, prefix: str, expires_in: int = 3600) -> str | None:
        """PDF Presigned URL 생성

        Args:
            prefix: S3 prefix (예: "canonical/pmc_PMC12345678")
            expires_in: URL 만료 시간 (초, 기본 1시간)

        Returns:
            Presigned URL 또는 None
        """
        try:
            # PDF 존재 확인
            self._client.head_object(
                Bucket=self.bucket,
                Key=f"{prefix}/paper.pdf",
            )

            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": f"{prefix}/paper.pdf",
                },
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def pdf_exists(self, prefix: str) -> bool:
        """PDF 존재 여부"""
        try:
            self._client.head_object(
                Bucket=self.bucket,
                Key=f"{prefix}/paper.pdf",
            )
            return True
        except ClientError:
            return False
