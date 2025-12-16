"""
OARIA Literature - 환경 설정

설정 방법:

옵션 1: 단일 모드 (스위칭 불가)
  MODE=local (또는 gcp)
  DATABASE_URL=postgresql://...

옵션 2: 런타임 스위칭 (프론트엔드에서 DB 전환 가능)
  MODE=local (초기 모드)
  LOCAL_DATABASE_URL=postgresql://...
  GCP_DATABASE_URL=mysql://...
  # DATABASE_URL은 불필요!
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Literal, Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 초기 모드: local 또는 gcp
    mode: Literal["local", "gcp"] = "local"
    
    # 기본 데이터베이스 URL (단일 모드용, 선택적)
    database_url: Optional[str] = None
    
    # 런타임 스위칭용 개별 URL
    local_database_url: Optional[str] = None
    gcp_database_url: Optional[str] = None
    
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
    
    # Embedding (configurable via EMBEDDING_MODEL and EMBEDDING_DIMENSION)
    # Options: 
    #   - "all-MiniLM-L6-v2" (384 dims, fast, general purpose)
    #   - "pritamdeka/S-PubMedBert-MS-MARCO" (768 dims, slower, biomedical specialized)
    embedding_model: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    embedding_dimension: int = 768
    embedding_batch_size: int = 64
    
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
    
    @property
    def supports_runtime_switching(self) -> bool:
        """런타임 DB 스위칭 가능 여부 (두 URL 모두 설정됨)"""
        return bool(self.local_database_url and self.gcp_database_url)
    
    def get_db_type_for_url(self, url: str) -> Literal["mysql", "postgresql"]:
        """주어진 URL의 데이터베이스 타입 감지"""
        url_lower = url.lower()
        if url_lower.startswith("mysql"):
            return "mysql"
        elif url_lower.startswith("postgresql") or url_lower.startswith("postgres"):
            return "postgresql"
        else:
            raise ValueError(f"지원하지 않는 데이터베이스: {url[:30]}...")
    
    def get_initial_database_url(self) -> str:
        """
        초기 DATABASE_URL 반환
        
        우선순위:
        1. 런타임 스위칭 모드면 MODE에 따라 선택
        2. DATABASE_URL이 있으면 사용
        3. 없으면 기본값
        """
        if self.supports_runtime_switching:
            # 런타임 스위칭 모드: MODE에 따라 선택
            if self.mode == "gcp" and self.gcp_database_url:
                return self.gcp_database_url
            elif self.local_database_url:
                return self.local_database_url
        
        # 단일 모드 또는 폴백
        if self.database_url:
            return self.database_url
        
        # 기본값 (Docker PostgreSQL)
        return "postgresql://oaria:oaria@db:5432/oaria"
    
    @property
    def db_type(self) -> Literal["mysql", "postgresql"]:
        """현재 활성 DATABASE_URL의 타입"""
        return self.get_db_type_for_url(self.get_initial_database_url())
    
    @property
    def uses_cloud_sql_socket(self) -> bool:
        """Cloud SQL 소켓 연결 여부"""
        url = self.get_initial_database_url()
        return "socket=" in url or "/cloudsql/" in url


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 인스턴스 반환"""
    return Settings()


# 런타임 활성 모드 (스위칭 가능)
_active_mode: Literal["local", "gcp"] = "local"


def get_active_mode() -> Literal["local", "gcp"]:
    """현재 활성 DB 모드 반환"""
    global _active_mode
    return _active_mode


def set_active_mode(mode: Literal["local", "gcp"]) -> bool:
    """활성 DB 모드 변경 (성공 여부 반환)"""
    global _active_mode
    settings = get_settings()
    
    if not settings.supports_runtime_switching:
        return False
    
    _active_mode = mode
    return True


def get_active_database_url() -> str:
    """현재 활성 모드에 맞는 DATABASE_URL 반환"""
    settings = get_settings()
    
    if settings.supports_runtime_switching:
        mode = get_active_mode()
        if mode == "local" and settings.local_database_url:
            return settings.local_database_url
        elif mode == "gcp" and settings.gcp_database_url:
            return settings.gcp_database_url
    
    return settings.get_initial_database_url()


# 편의를 위한 전역 접근
settings = get_settings()

# 초기 모드 설정
_active_mode = settings.mode
