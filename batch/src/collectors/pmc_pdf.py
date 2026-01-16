"""PMC PDF 다운로드 클라이언트

PMC Open Access PDF 다운로드
- OA 파일 목록: https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.txt
- PDF 접근: Europe PMC supplementaryFiles API 또는 PMC 웹 URL
"""

from dataclasses import dataclass, field

import httpx
import structlog

from ..config import settings

logger = structlog.get_logger()


@dataclass
class PMCPDFClient:
    """PMC PDF 다운로드 클라이언트"""

    timeout: float = 120.0  # PDF 다운로드는 오래 걸릴 수 있음
    max_pdf_size: int = 100 * 1024 * 1024  # 100MB 제한
    max_retries: int = 3

    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get_pdf_url(self, pmcid: str) -> str | None:
        """PMC PDF URL 조회

        PMC 웹 사이트의 PDF 다운로드 URL을 반환합니다.

        Args:
            pmcid: PMC ID (예: "PMC12345678")

        Returns:
            PDF URL 또는 None
        """
        # PMC 접두사 정규화
        if not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"

        # PMC 웹 PDF URL (직접 다운로드)
        # https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345678/pdf/
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

        return pdf_url

    async def check_pdf_available(self, pmcid: str) -> tuple[str | None, int | None]:
        """PDF 가용성 확인

        HEAD 요청으로 PDF가 존재하는지, 크기가 얼마인지 확인합니다.

        Args:
            pmcid: PMC ID

        Returns:
            (PDF URL, 파일 크기) 또는 (None, None)
        """
        pdf_url = await self.get_pdf_url(pmcid)
        if not pdf_url:
            return None, None

        try:
            response = await self._client.head(pdf_url)

            if response.status_code == 200:
                content_length = response.headers.get("content-length")
                size = int(content_length) if content_length else None

                # 크기 제한 확인
                if size and size > self.max_pdf_size:
                    logger.warning(
                        "pdf_too_large",
                        pmcid=pmcid,
                        size=size,
                        max_size=self.max_pdf_size,
                    )
                    return None, None

                return pdf_url, size

            logger.debug(
                "pdf_not_available",
                pmcid=pmcid,
                status=response.status_code,
            )
            return None, None

        except Exception as e:
            logger.warning(
                "pdf_check_failed",
                pmcid=pmcid,
                error=str(e),
            )
            return None, None

    async def download_pdf(self, pmcid: str) -> tuple[bytes, int] | None:
        """PDF 다운로드

        Args:
            pmcid: PMC ID

        Returns:
            (PDF bytes, size) 또는 None
        """
        pdf_url = await self.get_pdf_url(pmcid)
        if not pdf_url:
            return None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.get(pdf_url)

                if response.status_code == 200:
                    content = response.content
                    size = len(content)

                    # 크기 제한 확인
                    if size > self.max_pdf_size:
                        logger.warning(
                            "pdf_too_large",
                            pmcid=pmcid,
                            size=size,
                            max_size=self.max_pdf_size,
                        )
                        return None

                    # PDF 매직 바이트 확인
                    if not content.startswith(b"%PDF"):
                        logger.warning(
                            "pdf_invalid_format",
                            pmcid=pmcid,
                            preview=content[:50],
                        )
                        return None

                    logger.info(
                        "pdf_downloaded",
                        pmcid=pmcid,
                        size=size,
                        url=pdf_url,
                    )
                    return content, size

                elif response.status_code == 404:
                    logger.info("pdf_not_found", pmcid=pmcid)
                    return None

                elif response.status_code >= 500:
                    # 서버 에러 - 재시도
                    logger.warning(
                        "pdf_server_error",
                        pmcid=pmcid,
                        status=response.status_code,
                        attempt=attempt,
                    )
                    continue

                else:
                    logger.warning(
                        "pdf_download_failed",
                        pmcid=pmcid,
                        status=response.status_code,
                    )
                    return None

            except httpx.TimeoutException:
                logger.warning(
                    "pdf_download_timeout",
                    pmcid=pmcid,
                    attempt=attempt,
                )
                continue

            except Exception as e:
                logger.error(
                    "pdf_download_error",
                    pmcid=pmcid,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return None

        logger.error(
            "pdf_download_max_retries",
            pmcid=pmcid,
            max_retries=self.max_retries,
        )
        return None
