"""
OARIA Spike - 환경 설정

MODE 환경변수에 따라 자동으로 설정을 전환합니다:
- local: 로컬 PostgreSQL + 파일 시스템
- gcp: Cloud SQL + GCS

이 설계의 이유:
1. 단일 코드베이스로 로컬/클라우드 환경 모두 지원
2. 환경변수만 변경하면 자동 전환
3. 개발 시에는 로컬 모드로 빠르게 테스트
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 모드: local 또는 gcp
    mode: Literal["local", "gcp"] = "local"
    
    # 데이터베이스
    database_url: str = "postgresql://oaria:oaria@db:5432/oaria"
    
    # 스토리지
    storage_backend: Literal["local", "gcp"] = "local"
    local_storage_path: str = "/app/local_storage"
    gcs_bucket: str = ""
    
    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "papers"
    
    # PubMed API
    ncbi_api_key: str = ""
    pubmed_rate_limit: float = 3.0  # requests per second
    
    # Embedding
    embedding_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    embedding_dimension: int = 768
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def is_local(self) -> bool:
        """로컬 모드인지 확인"""
        return self.mode == "local"
    
    @property
    def is_gcp(self) -> bool:
        """GCP 모드인지 확인"""
        return self.mode == "gcp"
    
    @property
    def storage_is_local(self) -> bool:
        """스토리지가 로컬인지 확인"""
        return self.storage_backend == "local"


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 인스턴스 반환"""
    return Settings()


# 편의를 위한 전역 접근
settings = get_settings()
