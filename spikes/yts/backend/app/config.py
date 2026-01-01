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
