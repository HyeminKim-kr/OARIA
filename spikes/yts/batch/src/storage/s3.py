"""S3/MinIO 저장소

논문 원문(XML, fulltext) 저장
"""

from dataclasses import dataclass, field

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

        logger.info(
            "paper_saved_s3",
            paper_id=paper.paper_id,
            prefix=prefix,
            has_xml=paper.raw_xml is not None,
            has_fulltext=paper.fulltext is not None,
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
