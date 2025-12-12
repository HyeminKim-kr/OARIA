"""
OARIA Spike - 데이터베이스 연결

SQLAlchemy를 사용하여 PostgreSQL에 연결합니다.
로컬 모드와 GCP 모드 모두 동일한 인터페이스로 동작합니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager

from .config import settings

# SQLAlchemy 엔진 생성
engine = create_engine(
    settings.database_url,
    echo=False,  # SQL 로그 출력 (개발용: True)
    pool_pre_ping=True,  # 연결 상태 확인
    pool_size=5,
    max_overflow=10,
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (모든 모델이 상속)
Base = declarative_base()


def get_db():
    """FastAPI 의존성 주입용 DB 세션"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """컨텍스트 매니저용 DB 세션"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """데이터베이스 테이블 생성"""
    # 모든 모델을 import하여 메타데이터에 등록
    from .models import paper  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
