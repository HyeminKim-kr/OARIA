"""S3/MinIO 서비스

논문 원문(XML, display) 조회
"""

import json

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
        self._internal_endpoint = settings.s3_endpoint_url
        self._public_endpoint = settings.s3_public_endpoint_url

    def _make_url_public(self, url: str) -> str:
        """Convert internal S3 URL to public URL."""
        if self._internal_endpoint != self._public_endpoint:
            return url.replace(self._internal_endpoint, self._public_endpoint)
        return url

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

    def get_display(self, paper_id: str) -> dict | None:
        """논문 display.json 조회 (가독성용 섹션/문단 구조)

        Args:
            paper_id: 논문 ID

        Returns:
            display 딕셔너리 또는 None
        """
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/display.json"

        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def pdf_exists(self, paper_id: str) -> bool:
        """PDF 존재 여부 확인

        Args:
            paper_id: 논문 ID

        Returns:
            PDF 존재 여부
        """
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/paper.pdf"

        try:
            self._client.head_object(
                Bucket=self._bucket,
                Key=key,
            )
            return True
        except ClientError:
            return False

    def get_pdf_presigned_url(
        self, paper_id: str, expires_in: int = 3600
    ) -> str | None:
        """PDF Presigned URL 생성

        Args:
            paper_id: 논문 ID
            expires_in: URL 만료 시간 (초, 기본 1시간)

        Returns:
            Presigned URL 또는 None
        """
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/paper.pdf"

        try:
            # PDF 존재 확인
            self._client.head_object(
                Bucket=self._bucket,
                Key=key,
            )

            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def get_pdf(self, paper_id: str) -> bytes | None:
        """PDF 바이트 데이터 조회

        Args:
            paper_id: 논문 ID

        Returns:
            PDF 바이트 데이터 또는 None
        """
        safe_id = paper_id.replace(":", "_")
        key = f"canonical/{safe_id}/paper.pdf"

        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    async def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes data to S3.

        Args:
            data: Bytes to upload
            object_key: S3 object key (path)
            content_type: MIME type of the content

        Returns:
            URL of the uploaded object (public URL)
        """
        import asyncio

        # Run sync boto3 upload in thread pool
        def _upload():
            self._client.put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=data,
                ContentType=content_type,
            )
            # Return presigned URL for access
            url = self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": object_key,
                },
                ExpiresIn=86400 * 7,  # 7 days
            )
            return self._make_url_public(url)

        return await asyncio.to_thread(_upload)

    def upload_bytes_sync(
        self,
        data: bytes,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes data to S3 (synchronous version).

        Args:
            data: Bytes to upload
            object_key: S3 object key (path)
            content_type: MIME type of the content

        Returns:
            URL of the uploaded object
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
        # Return presigned URL for access
        return self._client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
            },
            ExpiresIn=86400 * 7,  # 7 days
        )


# 싱글톤 인스턴스
s3_service = S3Service()
