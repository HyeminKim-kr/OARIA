# -*- coding: utf-8 -*-
"""
Europe PMC API Server (FastAPI)

Python 백엔드를 통해 Europe PMC API를 호출하는 서버
viewer.html에서 이 서버를 호출하여 데이터를 가져옴

사용법:
    uv run uvicorn src.server:app --reload --port 8000

작성자: yts
작성일: 2025-12-22
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dataclasses import asdict

from .europe_pmc_client import EuropePMCClient

app = FastAPI(
    title="OAR-18: Europe PMC API",
    description="암 논문 수집 API - Europe PMC 연동",
    version="0.1.0"
)

# CORS 설정 (viewer.html에서 호출 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 클라이언트 인스턴스 (재사용)
client = EuropePMCClient(delay=0.3)


@app.get("/")
def root():
    """API 상태 확인"""
    return {
        "service": "OAR-18 Europe PMC API",
        "status": "running",
        "endpoints": {
            "/search": "논문 검색 (메타데이터 + 초록)",
            "/fulltext/{pmcid}": "전문 조회",
            "/search-with-fulltext": "검색 + 전문 수집"
        }
    }


@app.get("/search")
def search(
    query: str = Query(..., description="검색 쿼리"),
    limit: int = Query(10, ge=1, le=100, description="최대 결과 수"),
    open_access: bool = Query(True, description="Open Access만")
):
    """
    논문 검색 (메타데이터 + 초록)

    - **query**: 검색어 (예: "lung cancer", "neoplasms")
    - **limit**: 최대 결과 수 (1-100)
    - **open_access**: True면 OA 논문만 검색
    """
    result = client.search(
        query=query,
        limit=limit,
        open_access_only=open_access
    )

    return {
        "query": result["query"],
        "hit_count": result["hit_count"],
        "count": len(result["papers"]),
        "papers": [asdict(p) for p in result["papers"]]
    }


@app.get("/fulltext/{pmcid}")
def get_fulltext(pmcid: str):
    """
    개별 논문 전문 조회

    - **pmcid**: PMC ID (예: PMC12345678)
    """
    full_text = client.get_full_text(pmcid)

    if not full_text:
        return JSONResponse(
            status_code=404,
            content={"error": f"전문을 찾을 수 없음: {pmcid}"}
        )

    sections = client._parse_sections(full_text)

    return {
        "pmcid": pmcid,
        "full_text_length": len(full_text),
        "sections": sections
    }


@app.get("/search-with-fulltext")
def search_with_fulltext(
    query: str = Query(..., description="검색 쿼리"),
    limit: int = Query(5, ge=1, le=20, description="최대 결과 수 (전문 수집은 느림)")
):
    """
    논문 검색 + 전문 수집 (Open Access만)

    주의: 전문 수집은 논문당 약 0.5초 소요

    - **query**: 검색어
    - **limit**: 최대 결과 수 (1-20, 전문 수집 시간 고려)
    """
    papers = client.search_with_fulltext(
        query=query,
        limit=limit,
        verbose=False
    )

    return {
        "query": f"{query} AND OPEN_ACCESS:Y",
        "count": len(papers),
        "fulltext_count": sum(1 for p in papers if p.full_text),
        "papers": [asdict(p) for p in papers]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
