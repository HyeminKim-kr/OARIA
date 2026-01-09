"""RAG Config Manager

서버 시작 시 DB에서 RAG 설정을 로드하고 메모리에 캐시.
서비스 재시작 시에만 새 설정이 반영됨.
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RAGSettings

logger = logging.getLogger(__name__)


@dataclass
class LoadedRAGConfig:
    """로드된 RAG 설정"""

    name: str
    chunker: str
    embedder: str
    retriever: str
    reranker: str | None
    parameters: dict[str, Any]

    @property
    def limit(self) -> int:
        return self.parameters.get("limit", 10)

    @property
    def alpha(self) -> float:
        return self.parameters.get("alpha", 0.7)

    @property
    def min_rerank_score(self) -> float:
        return self.parameters.get("minRerankScore", 0.3)

    @property
    def temperature(self) -> float:
        return self.parameters.get("temperature", 0.7)


class RAGConfigManager:
    """RAG 설정 관리자

    싱글톤 패턴으로 구현. 서버 시작 시 한 번 로드되어 전역으로 사용.

    사용법:
        # 서버 시작 시
        await RAGConfigManager.load(db_session)

        # 사용 시
        config = RAGConfigManager.get()
        print(config.reranker)  # "bge"
    """

    _config: LoadedRAGConfig | None = None
    _loaded: bool = False

    @classmethod
    async def load(cls, db: AsyncSession) -> None:
        """DB에서 활성 설정을 로드

        Args:
            db: AsyncSession 인스턴스
        """
        try:
            result = await db.execute(
                select(RAGSettings).where(RAGSettings.is_active == True)  # noqa: E712
            )
            settings = result.scalar_one_or_none()

            if settings:
                cls._config = LoadedRAGConfig(
                    name=settings.name,
                    chunker=settings.chunker,
                    embedder=settings.embedder,
                    retriever=settings.retriever,
                    reranker=settings.reranker,
                    parameters=settings.parameters or {},
                )
                logger.info(
                    f"RAG config loaded: {settings.name} "
                    f"(chunker={settings.chunker}, embedder={settings.embedder}, "
                    f"retriever={settings.retriever}, reranker={settings.reranker})"
                )
            else:
                # 기본값 사용
                cls._config = LoadedRAGConfig(
                    name="default",
                    chunker="semantic",
                    embedder="openai",
                    retriever="hybrid",
                    reranker="bge",
                    parameters={"limit": 10, "alpha": 0.7},
                )
                logger.warning("No active RAG settings found, using defaults")

            cls._loaded = True

        except Exception as e:
            logger.error(f"Failed to load RAG config: {e}")
            # 에러 시에도 기본값으로 동작
            cls._config = LoadedRAGConfig(
                name="default",
                chunker="semantic",
                embedder="openai",
                retriever="hybrid",
                reranker="bge",
                parameters={"limit": 10, "alpha": 0.7},
            )
            cls._loaded = True

    @classmethod
    def get(cls) -> LoadedRAGConfig:
        """현재 로드된 설정 반환

        Returns:
            LoadedRAGConfig 인스턴스

        Raises:
            RuntimeError: 설정이 로드되지 않은 경우
        """
        if not cls._loaded or cls._config is None:
            raise RuntimeError(
                "RAG config not loaded. Call RAGConfigManager.load() at startup."
            )
        return cls._config

    @classmethod
    def is_loaded(cls) -> bool:
        """설정이 로드되었는지 확인"""
        return cls._loaded

    @classmethod
    def reset(cls) -> None:
        """설정 초기화 (테스트용)"""
        cls._config = None
        cls._loaded = False
