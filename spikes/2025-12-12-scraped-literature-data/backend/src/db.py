"""
OARIA Literature - 데이터베이스 연결 (Runtime Switching 지원)

SQLAlchemy를 사용하여 MySQL/PostgreSQL에 연결합니다.
LOCAL_DATABASE_URL과 GCP_DATABASE_URL이 모두 설정되면
런타임에 DB를 전환할 수 있습니다.

지원 형식:
- PostgreSQL: postgresql://user:pass@host:port/db
- MySQL: mysql://user:pass@host:port/db
- Cloud SQL: socket/host 파라미터 자동 변환
"""

from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Dict, Optional, Literal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.engine import Engine
from contextlib import contextmanager


from .config import (
    settings, 
    get_settings, 
    get_active_mode, 
    set_active_mode,
    get_active_database_url,
)


def _build_database_url(url: str, db_type: Literal["mysql", "postgresql"]) -> str:
    """DATABASE_URL을 SQLAlchemy 형식으로 변환"""
    if db_type == "mysql":
        # mysql:// → mysql+pymysql://
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        
        # Cloud SQL 소켓 처리: socket= → unix_socket=
        if "socket=" in url:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            if "socket" in query_params:
                socket_path = query_params.pop("socket")[0]
                query_params["unix_socket"] = [socket_path]
                netloc = parsed.netloc if parsed.netloc else "localhost"
                new_query = urlencode(query_params, doseq=True)
                url = urlunparse((
                    parsed.scheme, netloc, parsed.path,
                    parsed.params, new_query, parsed.fragment
                ))
    
    elif db_type == "postgresql":
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
    
    return url


def _create_engine_for_url(url: str, db_type: Literal["mysql", "postgresql"]) -> Engine:
    """주어진 URL에 대한 SQLAlchemy 엔진 생성"""
    processed_url = _build_database_url(url, db_type)
    return create_engine(
        processed_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600 if db_type == "mysql" else -1,
    )


# Base 클래스 (모든 모델이 상속)
Base = declarative_base()

# 데이터베이스 연결 풀 저장소
_engines: Dict[str, Engine] = {}
_session_factories: Dict[str, sessionmaker] = {}
_active_mode: Literal["local", "gcp"] = "local"


def _init_engines():
    """시작 시 엔진 초기화 (모든 설정된 DB에 대해)"""
    global _engines, _session_factories, _active_mode
    _settings = get_settings()
    _active_mode = _settings.mode
    
    # 디버그: 설정 상태 출력
    print(f"🔧 Config: MODE={_settings.mode}")
    print(f"   DATABASE_URL: {'✓ set' if _settings.database_url else '✗ not set'}")
    print(f"   LOCAL_DATABASE_URL: {'✓ set' if _settings.local_database_url else '✗ not set'}")
    print(f"   GCP_DATABASE_URL: {'✓ set' if _settings.gcp_database_url else '✗ not set'}")
    print(f"   supports_runtime_switching: {_settings.supports_runtime_switching}")
    
    # 런타임 스위칭 모드 (LOCAL + GCP 둘 다 설정됨)
    if _settings.supports_runtime_switching:
        # LOCAL 엔진
        if _settings.local_database_url:
            db_type = _settings.get_db_type_for_url(_settings.local_database_url)
            _engines["local"] = _create_engine_for_url(_settings.local_database_url, db_type)
            _session_factories["local"] = sessionmaker(autocommit=False, autoflush=False, bind=_engines["local"])
            print(f"📊 [LOCAL] DB 초기화: {db_type}")
        
        # GCP 엔진
        if _settings.gcp_database_url:
            db_type = _settings.get_db_type_for_url(_settings.gcp_database_url)
            _engines["gcp"] = _create_engine_for_url(_settings.gcp_database_url, db_type)
            _session_factories["gcp"] = sessionmaker(autocommit=False, autoflush=False, bind=_engines["gcp"])
            print(f"📊 [GCP] DB 초기화: {db_type}")
        
        print(f"🔄 런타임 스위칭 활성화 (초기 모드: {_active_mode})")
    
    # 단일 모드 (DATABASE_URL만 사용)
    elif _settings.database_url:
        db_type = _settings.db_type
        key = _settings.mode
        _engines[key] = _create_engine_for_url(_settings.database_url, db_type)
        _session_factories[key] = sessionmaker(autocommit=False, autoflush=False, bind=_engines[key])
        print(f"📊 [{key.upper()}] 단일 모드 DB 초기화: {db_type}")
    
    # 아무것도 설정 안 됨 - 기본값 사용
    else:
        default_url = "postgresql://oaria:oaria@db:5432/oaria"
        db_type = "postgresql"
        _engines["local"] = _create_engine_for_url(default_url, db_type)
        _session_factories["local"] = sessionmaker(autocommit=False, autoflush=False, bind=_engines["local"])
        print(f"📊 [LOCAL] 기본 Docker PG 초기화")


def get_current_engine() -> Engine:
    """현재 활성 모드의 엔진 반환"""
    if _active_mode in _engines:
        return _engines[_active_mode]
    # 폴백: 첫 번째 사용 가능한 엔진
    if _engines:
        return list(_engines.values())[0]
    raise RuntimeError("No database engine initialized")


def get_current_session_factory() -> sessionmaker:
    """현재 활성 모드의 세션 팩토리 반환"""
    if _active_mode in _session_factories:
        return _session_factories[_active_mode]
    if _session_factories:
        return list(_session_factories.values())[0]
    raise RuntimeError("No session factory initialized")


def switch_database(mode: Literal["local", "gcp"]) -> Dict:
    """런타임에 활성 데이터베이스 전환"""
    global _active_mode
    _settings = get_settings()
    
    if mode not in _engines:
        return {"success": False, "error": f"Mode '{mode}' not configured"}
    
    old_mode = _active_mode
    _active_mode = mode
    set_active_mode(mode)
    
    # 해당 모드의 db_type 가져오기
    if mode == "local" and _settings.local_database_url:
        db_type = _settings.get_db_type_for_url(_settings.local_database_url)
    elif mode == "gcp" and _settings.gcp_database_url:
        db_type = _settings.get_db_type_for_url(_settings.gcp_database_url)
    else:
        db_type = _settings.db_type
    
    # 연결 테스트
    try:
        with get_db_session() as db:
            db.execute(text("SELECT 1"))
        
        return {
            "success": True,
            "old_mode": old_mode,
            "new_mode": mode,
            "db_type": db_type,
            "connected": True,
            "message": f"Switched from {old_mode} to {mode}",
        }
    except Exception as e:
        # 실패 시 롤백
        _active_mode = old_mode
        set_active_mode(old_mode)
        return {"success": False, "error": str(e)}


# 커스텀 연결 정보 저장
_custom_connection_info: Dict = {}


def connect_custom_database(
    url: str,
    db_type: str,
    host: str,
    port: int,
    database: str,
    test_only: bool = False
) -> Dict:
    """커스텀 DB에 연결 (테스트 또는 실제 전환)"""
    global _active_mode, _custom_connection_info
    
    try:
        # 임시 엔진 생성하여 연결 테스트
        test_engine = _create_engine_for_url(url, db_type)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        if test_only:
            # 테스트만 하고 엔진 정리
            test_engine.dispose()
            return {
                "success": True,
                "message": "Connection test successful",
                "db_type": db_type,
                "host": host,
                "port": port,
                "database": database,
            }
        
        # 실제 전환 수행
        old_mode = _active_mode
        
        # 커스텀 엔진 등록
        _engines["custom"] = test_engine
        _session_factories["custom"] = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        
        # 커스텀 연결 정보 저장
        _custom_connection_info = {
            "host": host,
            "port": port,
            "database": database,
            "db_type": db_type,
            "connected_at": datetime.now().isoformat(),
        }
        
        # 활성 모드 변경
        _active_mode = "custom"
        set_active_mode("custom")
        
        return {
            "success": True,
            "old_mode": old_mode,
            "new_mode": "custom",
            "db_type": db_type,
            "host": host,
            "port": port,
            "database": database,
            "connected": True,
            "message": f"Connected to custom DB: {host}:{port}/{database}",
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_custom_connection_info() -> Dict:
    """현재 커스텀 연결 정보 반환"""
    return _custom_connection_info.copy() if _custom_connection_info else {}


def get_available_modes() -> Dict:
    """사용 가능한 DB 모드 목록 반환"""
    _settings = get_settings()
    modes = {}
    
    for mode, engine in _engines.items():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            connected = True
        except:
            connected = False
        
        # 해당 모드의 URL에서 DB 타입 추출
        if mode == "local" and _settings.local_database_url:
            db_type = _settings.get_db_type_for_url(_settings.local_database_url)
        elif mode == "gcp" and _settings.gcp_database_url:
            db_type = _settings.get_db_type_for_url(_settings.gcp_database_url)
        else:
            db_type = _settings.db_type
        
        modes[mode] = {
            "connected": connected,
            "db_type": db_type,
            "active": mode == _active_mode,
        }
    
    return {
        "active_mode": _active_mode,
        "supports_switching": _settings.supports_runtime_switching,
        "modes": modes,
    }


# 엔진 초기화
_init_engines()


# 하위 호환성을 위한 기존 변수들
engine = get_current_engine()
SessionLocal = get_current_session_factory()


def get_db():
    """FastAPI 의존성 주입용 DB 세션 (현재 활성 모드 사용)"""
    session_factory = get_current_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """컨텍스트 매니저용 DB 세션"""
    session_factory = get_current_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """모든 연결된 데이터베이스에 테이블 생성"""
    from .models import paper  # noqa: F401
    
    for mode, eng in _engines.items():
        try:
            Base.metadata.create_all(bind=eng)
            print(f"✅ [{mode.upper()}] Database tables created")
        except Exception as e:
            print(f"⚠️ [{mode.upper()}] Table creation failed: {e}")
