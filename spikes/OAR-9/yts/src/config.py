"""
설정 관리

환경변수 기반 설정 + Pydantic Settings
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """PostgreSQL 설정"""
    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=10932, alias="DB_PORT")  # OAR-9 고유 포트
    user: str = Field(default="oaria", alias="DB_USER")
    password: str = Field(default="oaria_dev", alias="DB_PASSWORD")
    database: str = Field(default="oaria", alias="DB_NAME")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = {"extra": "ignore"}


class S3Config(BaseSettings):
    """S3/MinIO 설정"""
    endpoint_url: str = Field(default="http://localhost:10900", alias="S3_ENDPOINT")  # OAR-9 고유 포트
    access_key: str = Field(default="minioadmin", alias="S3_ACCESS_KEY")
    secret_key: str = Field(default="minioadmin", alias="S3_SECRET_KEY")
    bucket: str = Field(default="oaria-papers", alias="S3_BUCKET")

    model_config = {"extra": "ignore"}


class APIConfig(BaseSettings):
    """Europe PMC API 설정"""
    max_concurrent: int = Field(default=10, alias="API_MAX_CONCURRENT")
    delay: float = Field(default=0.1, alias="API_DELAY")
    timeout: float = Field(default=60.0, alias="API_TIMEOUT")

    model_config = {"extra": "ignore"}


class Config(BaseSettings):
    """통합 설정"""
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    s3: S3Config = Field(default_factory=S3Config)
    api: APIConfig = Field(default_factory=APIConfig)

    model_config = {"extra": "ignore"}

    @classmethod
    def from_env(cls) -> "Config":
        """환경변수에서 설정 로드"""
        return cls(
            db=DatabaseConfig(),
            s3=S3Config(),
            api=APIConfig(),
        )
