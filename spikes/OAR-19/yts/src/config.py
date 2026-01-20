"""
설정 모듈
환경변수 기반 설정 관리
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 11932  # OAR-19 포트 규칙
    database: str = "oaria"
    user: str = "oaria"
    password: str = "oaria_dev"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class S3Config:
    endpoint_url: str = "http://localhost:11900"  # OAR-19 포트 규칙
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "oaria-papers"


@dataclass
class Config:
    db: DatabaseConfig
    s3: S3Config

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            db=DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "11932")),
                database=os.getenv("DB_NAME", "oaria"),
                user=os.getenv("DB_USER", "oaria"),
                password=os.getenv("DB_PASSWORD", "oaria_dev"),
            ),
            s3=S3Config(
                endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:11900"),
                access_key=os.getenv("S3_ACCESS_KEY", "minioadmin"),
                secret_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
                bucket=os.getenv("S3_BUCKET", "oaria-papers"),
            ),
        )


# 기본 설정 인스턴스
config = Config.from_env()
