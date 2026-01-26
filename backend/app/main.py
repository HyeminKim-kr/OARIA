"""OARIA Backend API"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .core import RAGConfigManager
from .core.rag_sync import sync_rag_strategies
from .database import async_session_maker
from .routers import (
    auth_router,
    papers_router,
    ai_router,
    lab_router,
    paper_chat_router,
    study_plan_router,
    agent_jobs_router,
    notifications_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리

    시작 시: RAG 설정 로드
    종료 시: 정리 작업
    """
    # Startup
    logger.info("Loading RAG configuration...")
    async with async_session_maker() as db:
        await RAGConfigManager.load(db)
    logger.info("RAG configuration loaded successfully")

    # RAG 전략 정보를 DB에 동기화
    logger.info("Syncing RAG strategies to DB...")
    async with async_session_maker() as db:
        result = await sync_rag_strategies(db)
    logger.info(f"RAG strategies synced: {result}")

    yield

    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="OARIA API",
    description="Backend API for OARIA",
    version="0.1.0",
    lifespan=lifespan,
)

# 세션 미들웨어 (OAuth용)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key,
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(papers_router)
app.include_router(ai_router)
app.include_router(paper_chat_router)  # 논문별 채팅
app.include_router(study_plan_router)  # Study Plan Agent
app.include_router(lab_router)  # RAG Lab (품질 테스트)
app.include_router(agent_jobs_router)  # Background Agent Jobs
app.include_router(notifications_router)  # Notifications


@app.get("/")
async def root():
    return {"message": "Welcome to OARIA API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
