"""애플리케이션 설정

Pydantic Settings를 사용한 환경변수 기반 설정
"""

from functools import lru_cache

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,  # alias와 필드명 모두 사용 가능
    )

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://oaria:oaria_dev_2024@localhost:15432/oaria",
        description="PostgreSQL 연결 URL (asyncpg 드라이버 사용)",
    )

    # Google OAuth
    google_client_id: str = Field(default="", description="Google OAuth Client ID")
    google_client_secret: str = Field(
        default="", description="Google OAuth Client Secret"
    )
    google_redirect_uri: str = Field(
        default="http://localhost:8000/auth/google/callback",
        description="Google OAuth Redirect URI",
    )

    # JWT
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="JWT 서명 키",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT 알고리즘")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Access Token 만료 시간 (분)"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh Token 만료 시간 (일)"
    )

    # Frontend
    frontend_url: str = Field(
        default="http://localhost:3000", description="프론트엔드 URL"
    )

    # App
    debug: bool = Field(default=True, description="디버그 모드")

    # Weaviate
    weaviate_host: str = Field(default="localhost", description="Weaviate 호스트")
    weaviate_port: int = Field(default=18080, description="Weaviate 포트")

    # S3/MinIO (batch와 동일한 환경변수명 사용)
    s3_endpoint_url: str = Field(
        default="http://localhost:19000",
        description="S3/MinIO 엔드포인트",
        alias="S3_ENDPOINT",
    )
    s3_access_key: str = Field(
        default="minioadmin",
        description="S3 Access Key",
        alias="S3_ACCESS_KEY",
    )
    s3_secret_key: str = Field(
        default="minioadmin_2024",
        description="S3 Secret Key",
        alias="S3_SECRET_KEY",
    )
    s3_bucket: str = Field(
        default="oaria-papers",
        description="S3 버킷 이름",
        alias="S3_BUCKET",
    )

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API 키")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", description="임베딩 모델"
    )
    openai_embedding_dimensions: int = Field(
        default=1536, description="임베딩 차원"
    )
    openai_chat_model: str = Field(
        default="gpt-4o-mini", description="챗 모델"
    )

    # v4 호환성 (openai_chat_model의 alias)
    @computed_field
    @property
    def openai_model(self) -> str:
        """v4 에이전트용 모델 설정 (openai_chat_model alias)"""
        return self.openai_chat_model

    # Redis (Study Plan Agent v3 - Budget/Cache)
    redis_url: str = Field(
        default="redis://localhost:16379",
        description="Redis 연결 URL (Budget Manager, Cache용)",
    )

    # Tavily (Web Search)
    tavily_api_key: str = Field(
        default="",
        description="Tavily API 키 (Web 검색용)",
    )

    # Study Plan Agent v3 - Search Budget
    search_web_monthly_limit: int = Field(
        default=1000,
        description="Tavily Web 검색 월간 제한 (무료 플랜 기준)",
    )
    search_web_per_run_limit: int = Field(
        default=1,
        description="단일 실행당 Web 검색 최대 횟수",
    )
    search_epmc_per_run_limit: int = Field(
        default=2,
        description="단일 실행당 Europe PMC 검색 최대 횟수",
    )

    @computed_field
    @property
    def database_url_sync(self) -> str:
        """동기 드라이버용 URL (Alembic용)"""
        return str(self.database_url).replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()


settings = get_settings()
