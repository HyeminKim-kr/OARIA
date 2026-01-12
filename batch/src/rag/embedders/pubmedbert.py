"""PubMedBERT 임베딩 전략

의생명 도메인에 특화된 PubMedBERT 기반 임베딩을 제공합니다.
sentence-transformers를 사용하여 문장 임베딩을 생성합니다.

모델: pritamdeka/S-PubMedBert-MS-MARCO
- PubMedBERT를 MS MARCO로 fine-tuning한 sentence-transformer 모델
- 768차원 벡터 출력
- 의생명 텍스트에 최적화
"""

import logging
import os
from typing import Any, Optional

import torch

from ..registry import register_embedder

logger = logging.getLogger(__name__)


def _get_best_device() -> str:
    """사용 가능한 최적 디바이스 반환

    Returns:
        'cuda', 'mps', 또는 'cpu'
    """
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@register_embedder
class PubMedBERTEmbedder:
    """PubMedBERT 기반 의생명 임베딩 (768차원)

    의생명 논문 및 텍스트에 특화된 임베딩 모델입니다.
    PubMed 코퍼스로 사전학습된 BERT를 사용합니다.

    장점:
    - 의생명 도메인 용어 이해도 높음
    - 논문 초록/본문 텍스트에 최적화
    - 로컬 실행 (API 비용 없음)

    단점:
    - GPU 없이는 느림
    - OpenAI 대비 낮은 차원 (768 vs 1536/3072)

    파라미터:
    - model: pritamdeka/S-PubMedBert-MS-MARCO
    - dimension: 768
    - max_seq_length: 512
    """

    name = "pubmedbert_768"
    dimension = 768

    # 기본 모델
    DEFAULT_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO"

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        max_seq_length: int = 512,
        normalize_embeddings: bool = True,
    ):
        """
        Args:
            model_name: 사용할 모델 이름 (없으면 환경변수 또는 기본값)
            device: 사용할 디바이스 (cuda/mps/cpu, 없으면 자동 감지)
            max_seq_length: 최대 토큰 길이
            normalize_embeddings: 임베딩 정규화 여부
        """
        self.model_name = model_name or os.getenv(
            "PUBMEDBERT_MODEL", self.DEFAULT_MODEL
        )
        self.device = device or _get_best_device()
        self.max_seq_length = max_seq_length
        self.normalize_embeddings = normalize_embeddings

        # Lazy loading
        self._model = None

        logger.info(
            f"PubMedBERTEmbedder initialized: model={self.model_name}, "
            f"device={self.device}, max_seq_length={max_seq_length}"
        )

    def _load_model(self):
        """모델 로드 (Lazy Loading)"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._model.max_seq_length = self.max_seq_length
            logger.info(f"Model loaded on {self.device}")

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩

        Args:
            text: 임베딩할 텍스트

        Returns:
            768차원 임베딩 벡터
        """
        self._load_model()

        # 빈 텍스트 처리
        if not text or not text.strip():
            text = " "

        embedding = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
        )

        return embedding.tolist()

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> list[list[float]]:
        """배치 텍스트 임베딩

        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 한 번에 처리할 텍스트 수
            show_progress: 진행률 표시 여부

        Returns:
            임베딩 벡터 리스트 (각 768차원)
        """
        self._load_model()

        # 빈 텍스트 처리
        processed_texts = [t if t and t.strip() else " " for t in texts]

        embeddings = self._model.encode(
            processed_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=show_progress,
        )

        return embeddings.tolist()

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "max_seq_length": self.max_seq_length,
            "normalize_embeddings": self.normalize_embeddings,
        }

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환 (Weaviate 저장용)"""
        # 모델 이름에서 슬래시 제거
        model_short = self.model_name.split("/")[-1] if "/" in self.model_name else self.model_name
        return f"pubmedbert:{model_short}:v1"


@register_embedder
class PubMedBERTLargeEmbedder:
    """PubMedBERT Large 기반 의생명 임베딩 (1024차원)

    더 큰 PubMedBERT 모델을 사용하여 더 풍부한 표현을 생성합니다.
    GPU 메모리가 충분한 경우 사용을 권장합니다.

    참고: Large 모델은 sentence-transformer로 fine-tuning된 버전이
    제한적일 수 있습니다. 필요시 모델명을 환경변수로 설정하세요.

    파라미터:
    - dimension: 1024
    - max_seq_length: 512
    """

    name = "pubmedbert_1024"
    dimension = 1024

    # 대형 모델 (fine-tuning 버전이 없으면 기본 모델 사용)
    DEFAULT_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO-SCIFACT"

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        max_seq_length: int = 512,
        normalize_embeddings: bool = True,
    ):
        """
        Args:
            model_name: 사용할 모델 이름
            device: 사용할 디바이스
            max_seq_length: 최대 토큰 길이
            normalize_embeddings: 임베딩 정규화 여부
        """
        self.model_name = model_name or os.getenv(
            "PUBMEDBERT_LARGE_MODEL", self.DEFAULT_MODEL
        )
        self.device = device or _get_best_device()
        self.max_seq_length = max_seq_length
        self.normalize_embeddings = normalize_embeddings

        self._model = None

        logger.info(
            f"PubMedBERTLargeEmbedder initialized: model={self.model_name}, "
            f"device={self.device}"
        )

    def _load_model(self):
        """모델 로드 (Lazy Loading)"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading large model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._model.max_seq_length = self.max_seq_length

            # 실제 차원 확인
            test_emb = self._model.encode("test")
            actual_dim = len(test_emb)
            if actual_dim != self.dimension:
                logger.warning(
                    f"Model dimension mismatch: expected {self.dimension}, "
                    f"got {actual_dim}. Updating dimension."
                )
                self.dimension = actual_dim

            logger.info(f"Large model loaded on {self.device}")

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        self._load_model()

        if not text or not text.strip():
            text = " "

        embedding = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
        )

        return embedding.tolist()

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> list[list[float]]:
        """배치 텍스트 임베딩"""
        self._load_model()

        processed_texts = [t if t and t.strip() else " " for t in texts]

        embeddings = self._model.encode(
            processed_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=show_progress,
        )

        return embeddings.tolist()

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "max_seq_length": self.max_seq_length,
            "normalize_embeddings": self.normalize_embeddings,
        }

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환"""
        model_short = self.model_name.split("/")[-1] if "/" in self.model_name else self.model_name
        return f"pubmedbert:{model_short}:v1"
