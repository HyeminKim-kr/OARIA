"""S3/MinIO 서비스

논문 원문(XML) 조회
"""

import boto3
from botocore.exceptions import ClientError

from ..config import settings


class S3Service:
    """S3/MinIO 서비스"""

    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        self._bucket = settings.s3_bucket

    def get_raw_xml(self, paper_id: str) -> str | None:
        """논문 원본 XML 조회

        Args:
            paper_id: 논문 ID (예: pmc:PMC12345678)

        Returns:
            XML 문자열 또는 None
        """
        # paper_id를 S3 경로로 변환: pmc:PMC12345678 → pmc_PMC12345678
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/raw.xml"

        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def get_fulltext(self, paper_id: str) -> str | None:
        """논문 fulltext 조회

        Args:
            paper_id: 논문 ID

        Returns:
            fulltext 문자열 또는 None
        """
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/fulltext.txt"

        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise


# 싱글톤 인스턴스
s3_service = S3Service()
