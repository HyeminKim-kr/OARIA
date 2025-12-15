"""
OARIA Literature - Paper ORM 모델

PubMed 논문 데이터를 저장하는 SQLAlchemy ORM 모델입니다.

테이블 구조:
- papers: 메타데이터 + Abstract + Full-text 경로
- embedding_tasks: 임베딩 작업 대기열

MySQL/PostgreSQL 둘 다 지원:
- PostgreSQL: JSONB 사용 (인덱싱, 연산자 지원)
- MySQL: JSON 사용
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, JSON, Enum, Integer
from sqlalchemy.types import TypeDecorator
import enum

from ..db import Base
from ..config import settings


# 데이터베이스에 따라 적절한 JSON 타입 선택
def get_json_type():
    """
    데이터베이스 타입에 따라 적절한 JSON 컬럼 타입 반환
    - PostgreSQL: JSONB (인덱싱, 연산자 지원)
    - MySQL: JSON
    """
    if settings.db_type == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB
    else:
        # MySQL 또는 기타 데이터베이스는 표준 JSON 사용
        return JSON


# 현재 데이터베이스에 맞는 JSON 타입
JSONType = get_json_type()


class EmbeddingStatus(str, enum.Enum):
    """임베딩 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Paper(Base):
    """
    논문 테이블
    
    PubMed와 PMC에서 수집한 논문 데이터를 저장합니다.
    """
    __tablename__ = "papers"
    
    # Primary Key
    pmid = Column(String(20), primary_key=True, index=True)
    
    # PMC ID (Open Access 논문만 존재)
    pmcid = Column(String(20), nullable=True, index=True)
    
    # 메타데이터
    title = Column(Text, nullable=False, default="")
    abstract = Column(Text, nullable=False, default="")
    authors = Column(JSONType, nullable=False, default=list)  # MySQL: JSON, PostgreSQL: JSONB
    journal = Column(String(500), nullable=True)
    pubdate = Column(String(50), nullable=True)
    doi = Column(String(200), nullable=True)
    mesh_terms = Column(JSONType, nullable=False, default=list)  # MySQL: JSON, PostgreSQL: JSONB
    
    # Full-text 저장 경로 (로컬 파일 경로 또는 GCS URL)
    fulltext_path = Column(Text, nullable=True)
    
    # 섹션별 텍스트 (PMC Full-text에서 추출)
    sections = Column(JSONType, nullable=True)  # MySQL: JSON, PostgreSQL: JSONB
    
    # 임베딩 상태
    embedding_status = Column(
        String(20),
        default=EmbeddingStatus.PENDING.value,
        index=True
    )
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Paper(pmid={self.pmid}, title={self.title[:50]}...)>"


class EmbeddingTask(Base):
    """
    임베딩 작업 대기열
    
    비동기 임베딩 처리를 위한 작업 대기열입니다.
    백그라운드 워커가 이 테이블을 폴링하여 작업을 처리합니다.
    """
    __tablename__ = "embedding_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pmid = Column(String(20), nullable=False, index=True)
    
    # 임베딩할 텍스트 (abstract 또는 section)
    text_type = Column(String(50), nullable=False, default="abstract")
    
    # 상태
    status = Column(
        String(20),
        default=EmbeddingStatus.PENDING.value,
        index=True
    )
    error_message = Column(Text, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<EmbeddingTask(id={self.id}, pmid={self.pmid}, status={self.status})>"

