"""설정 관리

환경변수 기반 설정 + Pydantic Settings
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """PostgreSQL 설정"""

    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=15432, alias="DB_PORT")
    user: str = Field(default="oaria", alias="DB_USER")
    password: str = Field(default="oaria_dev_2024", alias="DB_PASSWORD")
    database: str = Field(default="oaria", alias="DB_NAME")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = {"extra": "ignore"}


class S3Config(BaseSettings):
    """S3/MinIO 설정"""

    endpoint_url: str = Field(default="http://localhost:19000", alias="S3_ENDPOINT")
    access_key: str = Field(default="minioadmin", alias="S3_ACCESS_KEY")
    secret_key: str = Field(default="minioadmin_2024", alias="S3_SECRET_KEY")
    bucket: str = Field(default="oaria-papers", alias="S3_BUCKET")

    model_config = {"extra": "ignore"}


class RedisConfig(BaseSettings):
    """Redis 설정 (Celery 브로커)"""

    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=16379, alias="REDIS_PORT")
    db: int = Field(default=0, alias="REDIS_DB")

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"

    model_config = {"extra": "ignore"}


class APIConfig(BaseSettings):
    """Europe PMC API 설정"""

    base_url: str = Field(
        default="https://www.ebi.ac.uk/europepmc/webservices/rest",
        alias="EUROPE_PMC_BASE_URL",
    )
    rps_limit: float = Field(default=5.0, alias="API_RPS_LIMIT")
    max_concurrent: int = Field(default=3, alias="API_MAX_CONCURRENT")
    # 배치 작업이므로 타임아웃 여유롭게 (5분)
    timeout: float = Field(default=300.0, alias="API_TIMEOUT")
    max_retries: int = Field(default=5, alias="API_MAX_RETRIES")

    model_config = {"extra": "ignore"}


class Config(BaseSettings):
    """통합 설정"""

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    s3: S3Config = Field(default_factory=S3Config)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    model_config = {"extra": "ignore"}

    @classmethod
    def from_env(cls) -> "Config":
        """환경변수에서 설정 로드"""
        return cls(
            db=DatabaseConfig(),
            s3=S3Config(),
            redis=RedisConfig(),
            api=APIConfig(),
        )


# 싱글톤 설정 인스턴스
settings = Config.from_env()
