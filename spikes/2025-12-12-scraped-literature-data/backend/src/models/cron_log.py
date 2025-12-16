"""
OARIA Literature - CronLog 모델

크론 실행 기록을 저장하는 SQLAlchemy ORM 모델입니다.

테이블 구조:
- cron_logs: 각 크론 실행의 통계 기록
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer
from ..db import Base


class CronLog(Base):
    """
    크론 실행 기록 테이블
    
    각 ETL 크론 실행의 통계를 저장합니다.
    - 언제 실행했는지
    - 어떤 키워드로 검색했는지
    - 몇 개를 가져왔고, 저장했고, 스킵했는지
    - 실행 시간 (ms)
    """
    __tablename__ = "cron_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 실행 시각
    run_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 검색 키워드
    keyword = Column(String(255), nullable=False, index=True)
    
    # 통계
    fetched = Column(Integer, default=0)      # PubMed에서 가져온 수
    inserted = Column(Integer, default=0)     # 새로 저장된 수
    skipped = Column(Integer, default=0)      # 중복으로 스킵된 수
    
    # 실행 시간 (밀리초)
    duration_ms = Column(Integer, default=0)
    
    # 상태
    status = Column(String(20), default="success", index=True)  # success, error
    error_message = Column(Text, nullable=True)
    
    # PMID 범위 (신규 삽입된 논문)
    pmid_range_start = Column(String(20), nullable=True)
    pmid_range_end = Column(String(20), nullable=True)
    
    # 배치 위치 정보 (마지막 처리 위치 추적용)
    offset_start = Column(Integer, default=0)    # 이 배치의 시작 offset
    offset_end = Column(Integer, default=0)      # 이 배치의 끝 offset (다음 배치 시작점)
    
    # DB 전후 상태
    db_before = Column(Integer, default=0)    # 실행 전 총 논문 수
    db_after = Column(Integer, default=0)     # 실행 후 총 논문 수
    
    def __repr__(self):
        return f"<CronLog(id={self.id}, keyword={self.keyword}, inserted={self.inserted})>"
