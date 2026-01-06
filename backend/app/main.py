"""OARIA Backend API"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .routers import auth_router, papers_router, ai_router, lab_router

app = FastAPI(
    title="OARIA API",
    description="Backend API for OARIA",
    version="0.1.0",
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
app.include_router(lab_router)  # RAG Lab (품질 테스트)


@app.get("/")
async def root():
    return {"message": "Welcome to OARIA API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
