# F-02 & F-03 Functional Requirements Specification

## OARIA: Oncology AI Research Intelligence Assistant

### Infrastructure: OpenAlex + Qdrant + BGE-M3 + PostgreSQL

---

# F-02. 암 논문 자동 Batch 수집기 (Paper Crawler)

## 1. 기본 정보 (Basic Information)

| Field | Value |
|-------|-------|
| **기능 ID** | F-02 |
| **기능명** | 암 논문 자동 Batch 수집기 (Paper Crawler) |
| **우선순위** | P0 (Must Have) |
| **담당자** | Hyemin Kim (AI Lead) |
| **예상 개발 기간** | Week 1-2 (2주) |
| **의존성** | OpenAlex API, PostgreSQL |

---

## 2. 이게 뭔가요? (What is This? - Beginner Explanation)

### 2.1 우리가 해결하려는 문제

RAG 시스템이 작동하려면 검색할 논문이 필요합니다. 논문이 없으면 검색할 게 없습니다! 이 크롤러는 OpenAlex에서 암 연구 논문을 자동으로 다운로드해서 데이터베이스에 저장합니다.

### 2.2 OpenAlex가 뭔가요?

OpenAlex는 2억 5천만 개 이상의 학술 논문 정보를 담고 있는 무료 데이터베이스입니다. 도서관 카탈로그라고 생각하면 됩니다.

**왜 PubMed 대신 OpenAlex를 쓰나요?**

| 특징 | OpenAlex | PubMed |
|------|----------|--------|
| 논문 수 | 2억 5천만+ | 3천 5백만 |
| 암 연구 논문 | ✅ 모두 포함 | ✅ 포함 |
| API 사용료 | 무료 | 무료 |
| API 키 필요 | ❌ 불필요 | ⚠️ 권장 |
| 메타데이터 풍부도 | ✅ 인용수, 기관 등 | 기본적 |
| 페이지네이션 | 커서 기반 (효율적) | 오프셋 기반 |

OpenAlex는 PubMed의 모든 논문을 포함하면서, 더 나은 API와 풍부한 메타데이터를 제공합니다.

### 2.3 크롤러가 하는 일

```
1. OpenAlex에서 암 관련 논문 검색
2. 논문 메타데이터 다운로드 (제목, 초록, 저자 등)
3. PostgreSQL에 저장
4. 임베딩 작업 트리거 (논문을 검색 가능하게 만들기)
```

---

## 3. OpenAlex 핵심 개념

### 3.1 OpenAlex 데이터 구조

코드를 이해하려면 OpenAlex가 데이터를 어떻게 정리하는지 알아야 합니다:

**Works (논문)**: 개별 학술 논문. 우리가 다운로드하는 것.

**Concepts (개념)**: 주제/카테고리. OpenAlex가 자동으로 논문에 태그합니다.
- 예: "Cancer" (ID: C502942594), "Oncology" (ID: C126322002)

**Sources (출처)**: 논문이 게재된 저널, 학회지 등.

**Authors (저자)**: 논문 저자.

### 3.2 OpenAlex API 기본 사용법

```
기본 URL: https://api.openalex.org/

예시: 암 연구 논문 가져오기
https://api.openalex.org/works?filter=concepts.id:C126322002&per-page=200

응답: JSON 형태의 논문 목록
```

### 3.3 암 연구 관련 OpenAlex Concept IDs

| Concept | OpenAlex ID | 설명 |
|---------|-------------|------|
| Oncology | C126322002 | 종양학 |
| Cancer | C502942594 | 암 |
| Cancer research | C17744445 | 암 연구 |
| Tumor | C54355233 | 종양 |
| Neoplasm | C3019699 | 신생물 |
| Carcinoma | C158607117 | 암종 |
| Chemotherapy | C89423630 | 항암화학요법 |
| Immunotherapy | C2777844474 | 면역요법 |
| Radiation therapy | C71240020 | 방사선요법 |
| Targeted therapy | C555293320 | 표적치료 |
| EGFR | C14627729 | EGFR (폐암 관련 유전자) |
| BRCA | C75818621 | BRCA (유방암 관련 유전자) |
| TP53 | C44106959 | TP53 (암 억제 유전자) |

---

## 4. 수집 전략

### 4.1 검색 필터 설정

| 필터 | 설정 | 이유 |
|------|------|------|
| **Concepts** | 위 표의 Concept IDs | 암 연구 논문만 수집 |
| **출판 연도** | 2019-2025 (최근 6년) | 최신 연구에 집중 |
| **언어** | English (1차), Korean (2차) | 주요 논문 우선 |
| **논문 유형** | journal-article, review | 동료 심사 논문만 |
| **초록 유무** | has_abstract: true | RAG에 텍스트 필요 |

### 4.2 목표 수집량

| 단계 | 목표 | 기간 |
|------|------|------|
| 초기 MVP | 50,000건 | Week 1-2 |
| 전체 수집 | 100,000건+ | 지속적 |
| 일일 증분 | ~100-300건 | MVP 이후 |

---

## 5. 입력/출력 명세

### 5.1 크롤러 설정 (Input)

```python
from pydantic import BaseModel, Field
from datetime import date

class CrawlerConfig(BaseModel):
    """크롤러 설정"""
    
    # 검색할 Concept IDs (암 관련)
    concept_ids: list[str] = Field(
        default=[
            "C126322002",   # Oncology
            "C502942594",   # Cancer
            "C17744445",    # Cancer research
            "C54355233",    # Tumor
            "C89423630",    # Chemotherapy
            "C2777844474",  # Immunotherapy
        ],
        description="OpenAlex concept IDs to search"
    )
    
    # 날짜 범위
    from_date: date = Field(default=date(2019, 1, 1))
    to_date: date = Field(default_factory=date.today)
    
    # 수집량 제어
    max_results: int = Field(default=50000, description="최대 수집 건수")
    per_page: int = Field(default=200, description="API 호출당 건수 (최대 200)")
    
    # Rate limiting
    requests_per_second: float = Field(default=10, description="초당 최대 요청 수")
    
    # 식별용 이메일 (OpenAlex polite pool)
    email: str = Field(default="your-email@example.com")
```

### 5.2 논문 데이터 스키마 (Output)

PostgreSQL에 저장되는 각 논문의 구조:

```python
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class Author(BaseModel):
    """저자 정보"""
    name: str                          # "홍길동" 또는 "Jane Smith"
    orcid: Optional[str]               # ORCID ID (있는 경우)
    institution: Optional[str]         # 소속 기관
    country: Optional[str]             # 국가 코드

class Paper(BaseModel):
    """논문 레코드 - PostgreSQL에 저장"""
    
    # === 기본 식별자 ===
    openalex_id: str                   # "W2741809807" (Primary Key)
    
    # === 핵심 메타데이터 ===
    title: str                         # 논문 제목
    abstract: Optional[str]            # 초록 (RAG의 핵심!)
    
    # === 외부 식별자 ===
    doi: Optional[str]                 # "10.1038/s41586-021-03819-2"
    pmid: Optional[str]                # PubMed ID (있는 경우)
    
    # === 저자 정보 ===
    authors: list[Author]              # 저자 목록
    
    # === 출판 정보 ===
    publication_date: Optional[date]   # 출판일
    journal: Optional[str]             # "Nature Medicine"
    publisher: Optional[str]           # "Springer Nature"
    volume: Optional[str]
    issue: Optional[str]
    
    # === 분류 정보 ===
    concepts: list[dict]               # [{"id": "C123", "name": "Cancer", "score": 0.95}]
    topics: list[str]                  # 주제 분류
    keywords: list[str]                # 저자 키워드
    mesh_terms: list[str]              # MeSH 용어 (있는 경우)
    
    # === 접근성 ===
    is_open_access: bool               # 오픈 액세스 여부
    open_access_url: Optional[str]     # 무료 PDF URL (있는 경우)
    landing_page_url: Optional[str]    # 출판사 페이지
    
    # === 영향력 지표 ===
    cited_by_count: int                # 피인용 횟수
    
    # === 처리 상태 ===
    collected_at: datetime             # 수집 시각
    is_embedded: bool = False          # 임베딩 완료 여부
    embedding_error: Optional[str]     # 임베딩 실패 사유
```

### 5.3 PostgreSQL 스키마

```sql
-- 논문 테이블
CREATE TABLE papers (
    -- Primary key
    openalex_id VARCHAR(20) PRIMARY KEY,
    
    -- 핵심 내용
    title TEXT NOT NULL,
    abstract TEXT,
    
    -- 외부 식별자
    doi VARCHAR(100),
    pmid VARCHAR(20),
    
    -- 출판 정보
    publication_date DATE,
    journal VARCHAR(500),
    publisher VARCHAR(500),
    volume VARCHAR(50),
    issue VARCHAR(50),
    
    -- 분류 (JSONB로 유연하게 저장)
    concepts JSONB DEFAULT '[]',
    topics JSONB DEFAULT '[]',
    keywords JSONB DEFAULT '[]',
    mesh_terms JSONB DEFAULT '[]',
    
    -- 접근성
    is_open_access BOOLEAN DEFAULT FALSE,
    open_access_url TEXT,
    landing_page_url TEXT,
    
    -- 영향력
    cited_by_count INTEGER DEFAULT 0,
    
    -- 처리 상태
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_embedded BOOLEAN DEFAULT FALSE,
    embedding_error TEXT,
    
    -- 제약 조건: 초록이 있으면 최소 50자 이상
    CONSTRAINT abstract_min_length CHECK (abstract IS NULL OR LENGTH(abstract) >= 50)
);

-- 저자 테이블 (정규화)
CREATE TABLE paper_authors (
    id SERIAL PRIMARY KEY,
    openalex_id VARCHAR(20) REFERENCES papers(openalex_id) ON DELETE CASCADE,
    author_position INTEGER,  -- 1 = 제1저자, 2 = 제2저자, ...
    author_name VARCHAR(500) NOT NULL,
    orcid VARCHAR(50),
    institution VARCHAR(500),
    country VARCHAR(100)
);

-- 성능을 위한 인덱스
CREATE INDEX idx_papers_publication_date ON papers(publication_date DESC);
CREATE INDEX idx_papers_is_embedded ON papers(is_embedded) WHERE NOT is_embedded;
CREATE INDEX idx_papers_concepts ON papers USING GIN(concepts);
CREATE INDEX idx_papers_journal ON papers(journal);
CREATE INDEX idx_papers_cited_by ON papers(cited_by_count DESC);
CREATE INDEX idx_paper_authors_openalex ON paper_authors(openalex_id);
```

---

## 6. 처리 로직 (Processing Logic)

### 6.1 전체 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                    논문 크롤러 파이프라인                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: 검색 쿼리 구성                                           │
│ - Concept IDs를 API 필터로 조합                                  │
│ - 날짜 범위, 논문 유형 필터 추가                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: 페이지네이션으로 결과 순회                                │
│ - OpenAlex는 요청당 최대 200건 반환                              │
│ - 커서 기반 페이지네이션 사용 (효율적)                            │
│ - Rate limit 준수 (초당 10회)                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: 파싱 및 검증                                             │
│ - JSON 응답에서 필드 추출                                        │
│ - 초록 없는 논문 스킵                                            │
│ - 저자명, 소속 정규화                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: 중복 제거                                                │
│ - openalex_id로 기존 DB 확인                                     │
│ - 업데이트 시 변경된 데이터만 갱신                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: PostgreSQL에 Bulk Insert                                 │
│ - 배치 단위로 효율적 삽입 (500건씩)                               │
│ - 충돌 시 우아하게 처리 (UPSERT)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: 임베딩 작업 트리거                                        │
│ - 새 논문이 추가되면 임베딩 서비스에 알림                          │
│ - 비동기(큐) 또는 동기(즉시) 처리 가능                            │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 상세 구현

```python
"""
논문 크롤러 구현
파일: src/crawler/openalex_client.py
"""

import httpx
import asyncio
from datetime import date, datetime
from typing import AsyncGenerator
import structlog

from src.config.settings import settings
from src.crawler.models import Paper, Author, CrawlerConfig, CrawlResult

logger = structlog.get_logger()


class OpenAlexClient:
    """
    OpenAlex API 클라이언트
    
    OpenAlex는 세계 학술 논문의 무료 오픈 카탈로그입니다.
    문서: https://docs.openalex.org/
    """
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, email: str = None):
        """
        클라이언트 초기화
        
        Args:
            email: "polite pool"용 이메일 (더 빠른 rate limit 적용)
        """
        self.email = email or settings.OPENALEX_EMAIL
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": f"OARIA/1.0 (mailto:{self.email})"
            }
        )
    
    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.client.aclose()
    
    def _build_filter_string(self, config: CrawlerConfig) -> str:
        """
        OpenAlex API용 필터 문자열 구성
        
        OpenAlex 필터 문법:
        - 같은 필드의 여러 값: "|" 사용 (OR)
        - 다른 필드 간: "," 사용 (AND)
        
        예시: 
            concepts.id:C123|C456,publication_year:>2019
            = (concept C123 OR C456) AND (year > 2019)
        """
        filters = []
        
        # Concept 필터 (OR 조합)
        if config.concept_ids:
            concept_filter = "|".join(config.concept_ids)
            filters.append(f"concepts.id:{concept_filter}")
        
        # 날짜 범위
        if config.from_date:
            filters.append(f"publication_year:>{config.from_date.year - 1}")
        if config.to_date:
            filters.append(f"publication_year:<{config.to_date.year + 1}")
        
        # 초록이 있는 논문만 (RAG에 필수!)
        filters.append("has_abstract:true")
        
        # journal article과 review만 (preprint, dataset 등 제외)
        filters.append("type:journal-article|review")
        
        return ",".join(filters)
    
    async def search_papers(
        self, 
        config: CrawlerConfig
    ) -> AsyncGenerator[list[dict], None]:
        """
        설정에 맞는 논문 검색
        
        논문 배치를 yield하는 제너레이터입니다.
        커서 기반 페이지네이션으로 효율적으로 순회합니다.
        
        Yields:
            OpenAlex에서 온 논문 딕셔너리 배치
        """
        filter_string = self._build_filter_string(config)
        cursor = "*"  # 시작 커서
        total_fetched = 0
        
        logger.info(
            "논문_검색_시작",
            filter=filter_string,
            max_results=config.max_results
        )
        
        while cursor and total_fetched < config.max_results:
            # 요청 URL 구성
            params = {
                "filter": filter_string,
                "per-page": min(config.per_page, config.max_results - total_fetched),
                "cursor": cursor,
                "mailto": self.email,
            }
            
            try:
                response = await self.client.get(
                    f"{self.BASE_URL}/works",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                papers = data.get("results", [])
                if not papers:
                    break
                
                yield papers
                
                total_fetched += len(papers)
                cursor = data.get("meta", {}).get("next_cursor")
                
                logger.info(
                    "배치_완료",
                    batch_size=len(papers),
                    total_fetched=total_fetched
                )
                
                # Rate limiting: polite pool은 초당 10회 허용
                await asyncio.sleep(1 / config.requests_per_second)
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limit - 백오프
                    logger.warning("rate_limited", retry_after=60)
                    await asyncio.sleep(60)
                    continue
                raise
    
    def parse_paper(self, raw: dict) -> Paper | None:
        """
        OpenAlex 원시 데이터를 Paper 모델로 파싱
        
        Args:
            raw: OpenAlex API의 JSON dict
            
        Returns:
            Paper 객체, 또는 스킵해야 할 경우 None
        """
        # 초록 없으면 스킵 (RAG에 텍스트 필요)
        abstract = self._extract_abstract(raw)
        if not abstract or len(abstract) < 50:
            return None
        
        # 저자 파싱
        authors = []
        for authorship in raw.get("authorships", []):
            author = authorship.get("author", {})
            institutions = authorship.get("institutions", [])
            
            authors.append(Author(
                name=author.get("display_name", "Unknown"),
                orcid=author.get("orcid"),
                institution=institutions[0].get("display_name") if institutions else None,
                country=institutions[0].get("country_code") if institutions else None,
            ))
        
        # Concepts 파싱
        concepts = [
            {
                "id": c.get("id", "").split("/")[-1],
                "name": c.get("display_name"),
                "score": c.get("score", 0)
            }
            for c in raw.get("concepts", [])
            if c.get("score", 0) > 0.3  # 관련성 있는 것만
        ]
        
        # Paper 객체 생성
        return Paper(
            openalex_id=raw.get("id", "").split("/")[-1],
            title=raw.get("title", "Untitled"),
            abstract=abstract,
            doi=raw.get("doi"),
            pmid=raw.get("ids", {}).get("pmid"),
            authors=authors,
            publication_date=self._parse_date(raw.get("publication_date")),
            journal=raw.get("primary_location", {}).get("source", {}).get("display_name"),
            publisher=raw.get("primary_location", {}).get("source", {}).get("publisher"),
            concepts=concepts,
            topics=[t.get("display_name") for t in raw.get("topics", [])],
            keywords=raw.get("keywords", []) or [],
            mesh_terms=raw.get("mesh", []) or [],
            is_open_access=raw.get("open_access", {}).get("is_oa", False),
            open_access_url=raw.get("open_access", {}).get("oa_url"),
            landing_page_url=raw.get("primary_location", {}).get("landing_page_url"),
            cited_by_count=raw.get("cited_by_count", 0),
            collected_at=datetime.utcnow(),
        )
    
    def _extract_abstract(self, raw: dict) -> str | None:
        """
        OpenAlex 형식에서 초록 추출
        
        OpenAlex는 초록을 "inverted index" 형식으로 저장:
        {"abstract_inverted_index": {"word1": [0, 5], "word2": [1, 3], ...}}
        
        원래 텍스트로 재구성해야 합니다.
        """
        inverted = raw.get("abstract_inverted_index")
        if not inverted:
            return None
        
        # 재구성: (위치, 단어) 리스트 만들고 정렬 후 합치기
        words = []
        for word, positions in inverted.items():
            for pos in positions:
                words.append((pos, word))
        
        words.sort(key=lambda x: x[0])
        return " ".join(word for _, word in words)
    
    def _parse_date(self, date_str: str | None) -> date | None:
        """날짜 문자열을 date 객체로 파싱"""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None


async def crawl_papers(config: CrawlerConfig) -> CrawlResult:
    """
    논문 크롤링 메인 진입점
    
    이 함수는:
    1. OpenAlex에서 논문 가져오기
    2. 파싱 및 검증
    3. PostgreSQL에 저장
    4. 임베딩 작업 트리거
    
    Args:
        config: 크롤러 설정
        
    Returns:
        통계가 담긴 CrawlResult
    """
    from src.crawler.database import PaperRepository
    from src.rag.embedder import trigger_embedding_job
    
    client = OpenAlexClient(email=config.email)
    repo = PaperRepository()
    
    total_fetched = 0
    total_saved = 0
    total_skipped = 0
    errors = []
    
    try:
        async for batch in client.search_papers(config):
            papers = []
            
            for raw in batch:
                try:
                    paper = client.parse_paper(raw)
                    if paper:
                        papers.append(paper)
                    else:
                        total_skipped += 1
                except Exception as e:
                    errors.append(str(e))
                    logger.warning("파싱_에러", error=str(e))
            
            # DB에 Bulk insert
            saved = await repo.bulk_upsert(papers)
            
            total_fetched += len(batch)
            total_saved += saved
            
            logger.info(
                "배치_처리_완료",
                fetched=len(batch),
                parsed=len(papers),
                saved=saved,
                total_saved=total_saved
            )
        
        # 새 논문들에 대한 임베딩 작업 트리거
        await trigger_embedding_job()
        
    finally:
        await client.close()
    
    return CrawlResult(
        total_fetched=total_fetched,
        total_saved=total_saved,
        total_skipped=total_skipped,
        errors=errors
    )
```

---

## 7. 성공 기준 (Acceptance Criteria)

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 초기 수집 완료 | DB 논문 수 | ≥ 50,000건 |
| AC-2 | 메타데이터 완성도 | 초록 있는 논문 비율 | ≥ 95% |
| AC-3 | 수집 성공률 | (저장/가져오기) 비율 | ≥ 95% |
| AC-4 | 중복 방지 | 중복 openalex_id | 0건 |
| AC-5 | API 제한 준수 | 일일 429 에러 | ≤ 5회 |
| AC-6 | 수집 성능 | 분당 논문 수 | ≥ 500건 |

---

## 8. 예외 처리

| 예외 상황 | 처리 방법 | 재시도 |
|-----------|----------|--------|
| Rate Limit (429) | Exponential backoff: 30s → 60s → 120s | 최대 5회 |
| 네트워크 타임아웃 | 해당 배치 재시도 후 스킵 | 최대 3회 |
| 파싱 실패 | 로그 기록 후 해당 논문 스킵 | 재시도 없음 |
| DB 연결 실패 | 메모리 버퍼링 후 재연결 시도 | 무제한 |

---
---
---

# F-03. Evidence RAG 시스템

## 1. 기본 정보 (Basic Information)

| Field | Value |
|-------|-------|
| **기능 ID** | F-03 |
| **기능명** | Evidence RAG (검색 증강 생성) 시스템 |
| **우선순위** | P0 (Must Have) |
| **담당자** | Hyemin Kim (AI Lead) |
| **예상 개발 기간** | Week 2-4 (3주) |
| **의존성** | F-02 (논문 수집), BGE-M3, Qdrant |

---

## 2. RAG가 뭔가요? (완전 초보자 설명)

### 2.1 LLM의 문제점

대규모 언어 모델(LLM, 예: Claude)은 특정 시점까지의 데이터로 학습됩니다. 그래서 모르는 것이 있습니다:
- 최신 연구 논문
- 우리가 수집한 특정 문서들
- 학습 이후에 발표된 정보

모르는 것을 물어보면 LLM은 종종 **환각(hallucination)**합니다 - 그럴듯하지만 틀린 정보를 만들어냅니다.

### 2.2 RAG 해결책

RAG = **R**etrieval-**A**ugmented **G**eneration (검색 증강 생성)

```
기존 LLM:
사용자 질문 → LLM → 답변 (환각 가능성)

RAG:
사용자 질문 → 문서 검색 → LLM + 검색된 문서 → 답변 (근거 있음)
```

비유하자면:
- **RAG 없이**: 시험 볼 때 아무것도 없이 기억에만 의존하는 학생
- **RAG 있으면**: 시험 볼 때 관련 교과서 페이지를 찾아볼 수 있는 학생

### 2.3 RAG 파이프라인 시각적 개요

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           RAG 파이프라인 개요                               │
└────────────────────────────────────────────────────────────────────────────┘

오프라인 (사용자 질문 전): 지식 베이스 구축
═══════════════════════════════════════════

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  논문들   │───▶│  Chunker │───▶│ Embedder │───▶│  Qdrant  │
│ (50,000) │    │ (분할기)  │    │ (BGE-M3) │    │(벡터 DB) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘

    │               │               │               │
    │  "EGFR 변이   │  ~500 단어    │   숫자로      │   빠른 검색
    │   폐암..."    │   청크로 분할  │   변환(벡터)   │   위해 저장
    ▼               ▼               ▼               ▼


온라인 (사용자 질문 시): 질문 답변
════════════════════════════════

사용자: "EGFR 변이 폐암의 표적치료제 효과는?"
                    │
                    ▼
         ┌─────────────────────┐
         │  1. 질문 임베딩     │  질문을 벡터로 변환
         │     (BGE-M3)        │  [0.12, -0.34, 0.56, ...]
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  2. 벡터 검색       │  Qdrant에서 유사 벡터 찾기
         │     (Qdrant)        │  → 상위 10개 논문 청크 반환
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  3. 리랭킹          │  각 청크 관련성 정밀 평가
         │  (Cross-Encoder)    │  → 상위 5개 최고 청크 유지
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  4. 프롬프트 구성   │  질문 + 청크 조합
         │                     │  "다음 논문 참고: ... 답변: ..."
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  5. 답변 생성       │  LLM이 컨텍스트 읽고 답변
         │     (Claude API)    │  인용과 함께 [1], [2]
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  6. 인용 매핑       │  [1]을 실제 논문 정보로 연결
         │                     │  (제목, 저자, DOI)
         └──────────┬──────────┘
                    │
                    ▼
              최종 답변
              + 근거 논문
```

---

## 3. 서브 컴포넌트 상세 설명

### 3.1 Chunker: 논문을 조각으로 나누기

**왜 필요한가요?**
- LLM은 컨텍스트 제한이 있습니다 (50,000개 논문을 한 번에 못 읽음)
- 작은 조각이 검색 정밀도가 높습니다
- 논문 전체는 너무 크고, 문장 하나는 너무 작습니다

**무엇을 하나요?**
- 각 논문 초록을 ~512 토큰 청크로 분할
- 청크 간 50 토큰 오버랩 유지 (문장 중간에 잘리지 않도록)

```
논문 초록 (1000 토큰):
┌─────────────────────────────────────────────────────────────────────────────┐
│ "EGFR 변이는 비소세포폐암 환자에서 흔히 발견된다. 표적치료제는..."            │
└─────────────────────────────────────────────────────────────────────────────┘

청킹 후:
┌──────────────────────────────────────┐
│ 청크 1 (토큰 0-512)                  │
│ "EGFR 변이는 비소세포폐암 환자에서   │
│ 흔히 발견된다. 표적치료제는..."       │
└──────────────────────────────────────┘
                    │
                    │ 50 토큰 오버랩
                    ▼
         ┌──────────────────────────────────────┐
         │ 청크 2 (토큰 462-974)                │
         │ "...표적치료제는 erlotinib과         │
         │ gefitinib이 1차 치료로..."           │
         └──────────────────────────────────────┘
```

### 3.2 Embedder: 텍스트를 숫자로 변환

**왜 필요한가요?**
- 컴퓨터는 텍스트를 직접 이해 못합니다
- 텍스트를 벡터(숫자 리스트)로 변환해야 합니다
- 비슷한 의미 = 비슷한 벡터

**임베딩이 뭔가요?**
```
텍스트: "EGFR 변이 폐암"
    ↓
임베딩: [0.12, -0.34, 0.56, 0.78, -0.11, ..., 0.23]
        ← BGE-M3는 1024개 숫자 생성 →
```

**왜 BGE-M3인가요?**
- M3 = Multi-lingual(다국어), Multi-functionality(다기능), Multi-granularity(다단위)
- **Dense 벡터** (의미 검색용)와 **Sparse 벡터** (키워드 검색용) 둘 다 생성
- 오픈소스, 무료, 로컬 실행 가능
- 한국어도 지원!

### 3.3 Vector Store (Qdrant): 검색 데이터베이스

**왜 필요한가요?**
- 50,000개 논문 × 여러 청크 = 수백만 벡터 저장
- 빠른 유사도 검색 필요 (가장 가까운 이웃 찾기)

**유사도 검색 작동 방식:**
```
질문 벡터:    [0.12, -0.34, 0.56, ...]
                         ↓
                 가장 가까운 벡터 찾기
                         ↓
논문 A 벡터:  [0.11, -0.35, 0.55, ...]  ← 거리: 0.02 (매우 유사!)
논문 B 벡터:  [0.80, 0.20, -0.10, ...]  ← 거리: 0.89 (유사하지 않음)
논문 C 벡터:  [0.14, -0.30, 0.52, ...]  ← 거리: 0.05 (꽤 유사)
```

### 3.4 Hybrid Search: 두 세계의 장점

**의미 검색만의 문제:**
- "EGFR 변이"가 "수용체의 유전적 변화"와 매치될 수 있음
- 하지만 사용자가 "EGFR"을 입력하면 정확히 그 단어를 원할 수도 있음

**키워드 검색만의 문제:**
- "폐암 치료"가 "NSCLC therapy"와 매치 안 됨
- 동의어와 관련 개념을 놓침

**Hybrid Search는 둘을 결합:**
```
질문: "EGFR 폐암 표적치료"

의미 검색 결과:                    키워드 검색 결과:
1. "EGFR 신호전달 억제제"          1. "EGFR mutation targeted therapy"
2. "폐암 분자표적 요법"            2. "폐암 EGFR 치료"
3. "티로신 키나아제 억제제"        3. "표적치료제 EGFR"

결합 (Hybrid) 결과:
1. "EGFR 폐암 표적치료 효과" ← 두 방법의 장점!
2. "EGFR 신호전달 억제제"
3. "폐암 EGFR 치료"
```

### 3.5 Reranker: 검색 품질 향상

**왜 필요한가요?**
- 1단계 검색(임베딩)은 빠르지만 정밀도가 낮음
- Reranker는 느리지만 더 정확함
- 상위 후보에만 적용

**작동 방식:**
```
초기 검색: 20개 후보 반환 (빠름, ~50ms)
                        ↓
Reranker: 각 후보를 정밀 평가 (느림, ~500ms)
                        ↓
최종: 점수 가장 높은 5개 청크 유지
```

### 3.6 Generator: 답변 생성

**무엇을 하나요?**
- 질문 + 검색된 청크를 받음
- LLM (Claude API)에 전송
- 인라인 인용이 포함된 답변 받음

**중요한 규칙:**
- 제공된 청크의 정보만 사용
- 모든 주장에 [PMID:숫자] 형식 인용
- 청크에 답이 없으면 "모르겠습니다" 답변

---

## 4. 입력/출력 명세

### 4.1 RAG 질의 입력

```python
from pydantic import BaseModel, Field
from datetime import date

class RAGQuery(BaseModel):
    """RAG 질의 입력"""
    
    # 사용자 질문 (필수)
    query: str = Field(..., min_length=5, max_length=1000)
    
    # 초기에 검색할 문서 수
    top_k: int = Field(default=20, ge=5, le=50)
    
    # 리랭킹 후 유지할 문서 수
    top_n: int = Field(default=5, ge=3, le=10)
    
    # 전체 초록 포함 여부
    include_full_abstract: bool = Field(default=True)
    
    # 날짜 필터 (선택)
    date_from: date | None = None
    date_to: date | None = None
    
    # 최소 피인용 수 필터 (선택)
    min_citations: int | None = None
```

### 4.2 RAG 응답 출력

```python
from pydantic import BaseModel
from typing import Optional

class Evidence(BaseModel):
    """단일 근거 (인용된 논문)"""
    
    # 논문 식별
    openalex_id: str                    # "W2741809807"
    title: str                          # 논문 제목
    
    # 인용된 특정 텍스트
    cited_chunk: str                    # 사용된 청크 텍스트
    
    # 관련성 점수
    relevance_score: float              # 0.0 ~ 1.0 (reranker 점수)
    
    # 표시용 메타데이터
    authors: list[str]                  # ["Kim, J.", "Lee, S."]
    journal: Optional[str]              # "Nature Medicine"
    publication_date: Optional[date]    # 2024-03-15
    doi: Optional[str]                  # 링크용
    pmid: Optional[str]                 # PubMed 링크용
    
    # 답변에서 이 논문이 인용된 위치
    citation_markers: list[str]         # ["[1]", "[1]"] (두 번 인용되면)


class RAGResponse(BaseModel):
    """완전한 RAG 응답"""
    
    # 인라인 인용이 포함된 생성 답변
    answer: str
    # 예: "최근 연구에 따르면 EGFR 변이 폐암 환자에서 erlotinib은
    #      70%의 반응률을 보였다 [1]. 그러나 내성 발생이 문제다 [2]."
    
    # 인용된 모든 논문 목록
    evidence: list[Evidence]
    
    # 품질 지표
    retrieval_scores: list[float]       # 유사도 점수들
    avg_relevance: float                # 평균 reranker 점수
    
    # 성능
    processing_time_ms: int             # 총 처리 시간
    
    # Gate 2 정보 (투명성)
    gate2_passed: bool
    gate2_details: dict                 # {"max_similarity": 0.85, ...}


class RAGError(BaseModel):
    """RAG 실패 시 에러 응답"""
    
    error_type: str                     # "insufficient_evidence", "gate_failed" 등
    message: str                        # 사용자 친화적 메시지
    suggestion: str                     # 질문 개선 방법
```

---

## 5. Qdrant 컬렉션 스키마

### 5.1 Qdrant 컬렉션이란?

Qdrant의 컬렉션은 데이터베이스의 테이블과 비슷하지만 벡터에 최적화되어 있습니다. 각 아이템("point")은:
- 고유 ID
- 벡터 (또는 hybrid search용 여러 벡터)
- 페이로드 (메타데이터)

### 5.2 컬렉션 설정

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, 
    Distance, 
    SparseVectorParams,
    SparseIndexParams,
)

def create_collection(client: QdrantClient):
    """
    암 논문 청크용 Qdrant 컬렉션 생성
    
    Hybrid search 사용:
    - Dense 벡터: 의미 유사도 (BGE-M3 dense)
    - Sparse 벡터: 키워드 매칭 (BGE-M3 sparse/lexical)
    """
    
    client.create_collection(
        collection_name="oncology_papers",  # 컬렉션 이름
        
        # Dense 벡터 설정
        vectors_config={
            "dense": VectorParams(
                size=1024,           # BGE-M3 dense 차원
                distance=Distance.COSINE,
            )
        },
        
        # Sparse 벡터 설정 (hybrid search용)
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(
                    on_disk=False,   # 속도를 위해 메모리에 유지
                )
            )
        },
    )
```

### 5.3 Point (문서) 스키마

```python
from qdrant_client.models import PointStruct, SparseVector

def create_point(
    chunk_id: str,
    chunk_text: str,
    dense_vector: list[float],
    sparse_vector: tuple[list[int], list[float]],
    paper_metadata: dict
) -> PointStruct:
    """
    논문 청크용 Qdrant point 생성
    
    Args:
        chunk_id: 고유 식별자 "W12345_chunk_0"
        chunk_text: 실제 텍스트 내용
        dense_vector: 1024차원 dense 임베딩
        sparse_vector: Sparse 임베딩 (토큰 ID와 가중치)
        paper_metadata: 검색용 논문 정보
    """
    
    return PointStruct(
        id=chunk_id,
        
        vector={
            "dense": dense_vector,
            "sparse": SparseVector(
                indices=sparse_vector[0],
                values=sparse_vector[1]
            )
        },
        
        payload={
            # === 텍스트 내용 ===
            "text": chunk_text,
            "chunk_index": 0,
            
            # === 논문 식별자 ===
            "openalex_id": "W12345",
            "doi": "10.1000/example",
            "pmid": "12345678",
            
            # === 표시용 메타데이터 ===
            "title": "논문 제목",
            "authors": ["Kim, J.", "Lee, S."],
            "journal": "Nature Medicine",
            "publication_date": "2024-03-15",
            
            # === 필터링 필드 ===
            "publication_year": 2024,
            "cited_by_count": 150,
            "is_open_access": True,
            
            # === Concepts (필터링/패싯용) ===
            "concepts": ["oncology", "egfr", "lung_cancer"],
        }
    )
```

---

## 6. 처리 로직: 완전한 파이프라인

### 6.1 오프라인 파이프라인: 논문 인덱싱

초기에 한 번 실행하고, 새 논문 추가 시 증분 실행합니다.

```python
"""
오프라인 인덱싱 파이프라인
파일: src/rag/indexer.py
"""

import asyncio
from typing import Generator
import structlog
from FlagEmbedding import BGEM3FlagModel
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

from src.config.settings import settings
from src.crawler.database import PaperRepository

logger = structlog.get_logger()


class PaperIndexer:
    """
    PostgreSQL의 논문을 Qdrant에 인덱싱
    
    RAG의 "오프라인" 부분 - 검색 가능한 인덱스 구축
    """
    
    def __init__(self):
        # BGE-M3 모델 (dense + sparse 임베딩 생성)
        # 주의: 모델이 크므로 (~2GB) 한 번만 로드!
        logger.info("BGE-M3 모델 로딩 중...")
        self.model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
        logger.info("BGE-M3 모델 로드 완료")
        
        # Qdrant 클라이언트
        self.qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        
        # PostgreSQL 레포지토리
        self.paper_repo = PaperRepository()
        
        # 청킹 파라미터
        self.chunk_size = 512      # 토큰
        self.chunk_overlap = 50    # 토큰
    
    def chunk_text(self, text: str) -> list[str]:
        """
        텍스트를 오버랩되는 청크로 분할
        
        왜 오버랩?
        - 중요한 문장이 중간에 잘리는 것 방지
        - 청크 간 문맥 연속성 유지
        
        Args:
            text: 청킹할 전체 텍스트
            
        Returns:
            텍스트 청크 리스트
        """
        if not text:
            return []
        
        # 간단한 단어 기반 청킹
        words = text.split()
        chunks = []
        
        # 대략: 영어 1토큰 ≈ 0.75 단어
        words_per_chunk = int(self.chunk_size * 0.75)
        overlap_words = int(self.chunk_overlap * 0.75)
        
        start = 0
        while start < len(words):
            end = start + words_per_chunk
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            
            start = end - overlap_words
            
            if start <= 0 and end >= len(words):
                break
        
        return chunks
    
    def embed_texts(self, texts: list[str]) -> tuple[list, list]:
        """
        BGE-M3로 텍스트 임베딩 생성
        
        BGE-M3는 둘 다 반환:
        - Dense 임베딩: 의미 검색용 1024차원 벡터
        - Sparse 임베딩: 키워드 검색용 토큰-가중치 쌍
        
        Returns:
            (dense_embeddings, sparse_embeddings)
        """
        outputs = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        
        dense_embeddings = outputs["dense_vecs"]
        
        # Sparse 임베딩을 Qdrant 형식으로 변환
        sparse_embeddings = []
        for sparse_dict in outputs["lexical_weights"]:
            indices = list(sparse_dict.keys())
            values = list(sparse_dict.values())
            sparse_embeddings.append((indices, values))
        
        return dense_embeddings, sparse_embeddings
    
    async def index_paper(self, paper) -> int:
        """
        단일 논문을 Qdrant에 인덱싱
        
        Returns:
            인덱싱된 청크 수
        """
        if paper.is_embedded:
            return 0
        
        if not paper.abstract:
            logger.warning("초록_없음_스킵", paper_id=paper.openalex_id)
            return 0
        
        # 제목 + 초록으로 청크 생성
        full_text = f"{paper.title}\n\n{paper.abstract}"
        chunks = self.chunk_text(full_text)
        
        if not chunks:
            return 0
        
        # 모든 청크에 대해 임베딩 생성
        dense_vecs, sparse_vecs = self.embed_texts(chunks)
        
        # Qdrant points 생성
        points = []
        for i, (chunk, dense, sparse) in enumerate(zip(chunks, dense_vecs, sparse_vecs)):
            point = PointStruct(
                id=f"{paper.openalex_id}_chunk_{i}",
                vector={
                    "dense": dense.tolist(),
                    "sparse": SparseVector(
                        indices=sparse[0],
                        values=sparse[1]
                    )
                },
                payload={
                    "text": chunk,
                    "chunk_index": i,
                    "openalex_id": paper.openalex_id,
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors[:5]],
                    "journal": paper.journal,
                    "publication_date": str(paper.publication_date) if paper.publication_date else None,
                    "publication_year": paper.publication_date.year if paper.publication_date else None,
                    "doi": paper.doi,
                    "pmid": paper.pmid,
                    "cited_by_count": paper.cited_by_count,
                    "is_open_access": paper.is_open_access,
                    "concepts": [c["name"] for c in paper.concepts[:10]],
                }
            )
            points.append(point)
        
        # Qdrant에 upsert
        self.qdrant.upsert(
            collection_name="oncology_papers",
            points=points
        )
        
        # PostgreSQL에 임베딩 완료 표시
        await self.paper_repo.mark_embedded(paper.openalex_id)
        
        return len(points)
    
    async def index_all_papers(self, batch_size: int = 100):
        """
        임베딩되지 않은 모든 논문 인덱싱
        
        벌크 인덱싱의 메인 진입점
        """
        total_chunks = 0
        total_papers = 0
        
        async for papers in self.paper_repo.get_unembedded_papers(batch_size):
            for paper in papers:
                try:
                    chunks = await self.index_paper(paper)
                    total_chunks += chunks
                    total_papers += 1
                    
                    if total_papers % 100 == 0:
                        logger.info(
                            "인덱싱_진행",
                            papers=total_papers,
                            chunks=total_chunks
                        )
                except Exception as e:
                    logger.error(
                        "인덱싱_에러",
                        paper_id=paper.openalex_id,
                        error=str(e)
                    )
        
        logger.info(
            "인덱싱_완료",
            total_papers=total_papers,
            total_chunks=total_chunks
        )
```

### 6.2 온라인 파이프라인: 질의 응답

사용자가 질문할 때마다 실행됩니다.

```python
"""
온라인 RAG 파이프라인
파일: src/rag/pipeline.py
"""

import time
from typing import Optional
import structlog
from FlagEmbedding import BGEM3FlagModel, FlagReranker
from qdrant_client import QdrantClient
from qdrant_client.models import (
    SearchRequest,
    NamedVector,
    NamedSparseVector,
    SparseVector,
    Filter,
    FieldCondition,
    Range,
)
import anthropic

from src.config.settings import settings
from src.rag.models import RAGQuery, RAGResponse, Evidence
from src.gates.gate2_retrieval import check_retrieval_confidence

logger = structlog.get_logger()


class RAGPipeline:
    """
    질문 답변을 위한 메인 RAG 파이프라인
    
    흐름:
    1. 쿼리 임베딩 (BGE-M3)
    2. Qdrant에서 Hybrid search (dense + sparse)
    3. Cross-encoder로 리랭킹
    4. 컨텍스트로 프롬프트 구성
    5. Claude로 답변 생성
    6. 인용 매핑
    """
    
    def __init__(self):
        logger.info("RAG 파이프라인 초기화 중...")
        
        # 임베딩 모델 (인덱싱과 동일)
        self.embedder = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
        
        # Reranker: 더 정확한 관련성 평가를 위한 Cross-encoder
        self.reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)
        
        # Qdrant 클라이언트
        self.qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        
        # 답변 생성용 Claude 클라이언트
        self.claude = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        
        logger.info("RAG 파이프라인 준비 완료")
    
    def _embed_query(self, query: str) -> tuple[list[float], tuple[list, list]]:
        """
        BGE-M3로 쿼리 임베딩
        
        Hybrid search를 위해 dense와 sparse 벡터 둘 다 반환
        """
        outputs = self.embedder.encode(
            [query],
            return_dense=True,
            return_sparse=True,
        )
        
        dense = outputs["dense_vecs"][0].tolist()
        sparse_dict = outputs["lexical_weights"][0]
        sparse = (list(sparse_dict.keys()), list(sparse_dict.values()))
        
        return dense, sparse
    
    async def _hybrid_search(
        self, 
        query: str,
        dense_vector: list[float],
        sparse_vector: tuple[list, list],
        top_k: int,
        filters: Optional[Filter] = None
    ) -> list[dict]:
        """
        Qdrant에서 Hybrid search 수행
        
        Hybrid search 결합:
        - Dense search: 의미 유사도 (의미 이해)
        - Sparse search: 키워드 매칭 (정확한 키워드 찾기)
        
        결과는 Reciprocal Rank Fusion (RRF)으로 병합
        """
        results = self.qdrant.query_points(
            collection_name="oncology_papers",
            prefetch=[
                SearchRequest(
                    vector=NamedVector(name="dense", vector=dense_vector),
                    limit=top_k,
                    filter=filters,
                ),
                SearchRequest(
                    vector=NamedSparseVector(
                        name="sparse",
                        vector=SparseVector(
                            indices=sparse_vector[0],
                            values=sparse_vector[1]
                        )
                    ),
                    limit=top_k,
                    filter=filters,
                ),
            ],
            query={"fusion": "rrf"},
            limit=top_k,
        )
        
        documents = []
        for point in results.points:
            documents.append({
                "id": point.id,
                "score": point.score,
                "text": point.payload["text"],
                "openalex_id": point.payload["openalex_id"],
                "title": point.payload["title"],
                "authors": point.payload.get("authors", []),
                "journal": point.payload.get("journal"),
                "publication_date": point.payload.get("publication_date"),
                "doi": point.payload.get("doi"),
                "pmid": point.payload.get("pmid"),
            })
        
        return documents
    
    def _rerank(
        self, 
        query: str, 
        documents: list[dict], 
        top_n: int
    ) -> list[dict]:
        """
        Cross-encoder로 문서 리랭킹
        
        Cross-encoder는 bi-encoder보다 정확함
        쿼리와 문서를 함께 처리해서 더 깊은 상호작용 허용
        
        트레이드오프: 훨씬 느리므로 상위 후보에만 적용
        """
        if not documents:
            return []
        
        pairs = [(query, doc["text"]) for doc in documents]
        scores = self.reranker.compute_score(pairs)
        
        # 문서에 점수 추가
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)
        
        documents.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        return documents[:top_n]
    
    def _build_prompt(self, query: str, documents: list[dict]) -> str:
        """
        Claude용 프롬프트 구성
        
        프롬프트 구조가 RAG 품질에 중요:
        1. 명확한 시스템 지시
        2. 잘 포맷된 컨텍스트
        3. 실제 질문
        4. 형식 요구사항
        """
        context_parts = []
        for i, doc in enumerate(documents, 1):
            # 저자 포맷 (3명 이상이면 "et al.")
            authors = doc.get("authors", [])
            if len(authors) > 3:
                author_str = ", ".join(authors[:3]) + " et al."
            else:
                author_str = ", ".join(authors) if authors else "Unknown"
            
            context_parts.append(f"""
[{i}] {doc['title']}
저자: {author_str}
저널: {doc.get('journal', 'Unknown')} ({doc.get('publication_date', 'Unknown')})
DOI: {doc.get('doi', 'N/A')}

{doc['text']}
---""")
        
        context = "\n".join(context_parts)
        
        prompt = f"""당신은 암 연구 전문 AI 어시스턴트입니다.
아래 제공된 논문 정보만을 근거로 질문에 답변하세요.

규칙:
1. 제공된 논문에 없는 내용은 답변하지 마세요
2. 각 주장에 [1], [2] 등 논문 번호로 출처를 표기하세요
3. 불확실한 내용은 "~로 알려져 있습니다", "~를 시사합니다" 등으로 표현하세요
4. 임상적 결정을 직접 권유하지 마세요
5. 외부 지식이나 만들어낸 정보를 사용하지 마세요

참고 논문:
{context}

질문: {query}

위 논문들을 참고하여 인용과 함께 종합적인 답변을 제공해 주세요."""
        
        return prompt
    
    async def _generate_answer(self, prompt: str) -> str:
        """Claude로 답변 생성"""
        response = await self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text
    
    def _extract_citations(
        self, 
        answer: str, 
        documents: list[dict]
    ) -> list[Evidence]:
        """
        답변에서 인용 마커 추출하고 문서에 매핑
        
        [1], [2], [1,3] 등의 패턴 찾기
        """
        import re
        
        evidence = []
        citation_pattern = r'\[(\d+(?:,\s*\d+)*)\]'
        
        for doc_index, doc in enumerate(documents, 1):
            markers = []
            for match in re.finditer(citation_pattern, answer):
                cited_numbers = [int(n.strip()) for n in match.group(1).split(",")]
                if doc_index in cited_numbers:
                    markers.append(f"[{doc_index}]")
            
            if markers:
                evidence.append(Evidence(
                    openalex_id=doc["openalex_id"],
                    title=doc["title"],
                    cited_chunk=doc["text"][:500] + "..." if len(doc["text"]) > 500 else doc["text"],
                    relevance_score=doc.get("rerank_score", doc["score"]),
                    authors=doc.get("authors", []),
                    journal=doc.get("journal"),
                    publication_date=doc.get("publication_date"),
                    doi=doc.get("doi"),
                    pmid=doc.get("pmid"),
                    citation_markers=list(set(markers)),
                ))
        
        return evidence
    
    async def query(self, request: RAGQuery) -> RAGResponse:
        """
        메인 진입점: RAG로 질문 답변
        
        전체 파이프라인 조율:
        1. 쿼리 임베딩
        2. Hybrid search
        3. 리랭킹
        4. Gate 2 검사
        5. 답변 생성
        6. 인용 추출
        """
        start_time = time.time()
        
        logger.info("rag_query_시작", query=request.query)
        
        # Step 1: 쿼리 임베딩
        dense_vec, sparse_vec = self._embed_query(request.query)
        
        # Step 2: 필터 구성 (선택)
        filters = None
        if request.date_from or request.date_to or request.min_citations:
            conditions = []
            if request.date_from:
                conditions.append(
                    FieldCondition(
                        key="publication_year",
                        range=Range(gte=request.date_from.year)
                    )
                )
            if request.min_citations:
                conditions.append(
                    FieldCondition(
                        key="cited_by_count",
                        range=Range(gte=request.min_citations)
                    )
                )
            if conditions:
                filters = Filter(must=conditions)
        
        # Step 3: Hybrid search
        documents = await self._hybrid_search(
            query=request.query,
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            top_k=request.top_k,
            filters=filters
        )
        
        # Step 4: 리랭킹
        reranked_docs = self._rerank(
            query=request.query,
            documents=documents,
            top_n=request.top_n
        )
        
        # Step 5: Gate 2 - 검색 신뢰도 검사
        gate2_result = check_retrieval_confidence(request.query, reranked_docs)
        
        if not gate2_result.passed:
            return RAGResponse(
                answer="",
                evidence=[],
                retrieval_scores=[d["score"] for d in documents[:5]],
                avg_relevance=0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                gate2_passed=False,
                gate2_details={
                    "reason": gate2_result.reason,
                    "message": gate2_result.message,
                }
            )
        
        # Step 6: 프롬프트 구성 및 생성
        prompt = self._build_prompt(request.query, reranked_docs)
        answer = await self._generate_answer(prompt)
        
        # Step 7: 인용 추출
        evidence = self._extract_citations(answer, reranked_docs)
        
        processing_time = int((time.time() - start_time) * 1000)
        avg_relevance = sum(d.get("rerank_score", 0) for d in reranked_docs) / len(reranked_docs) if reranked_docs else 0
        
        logger.info(
            "rag_query_완료",
            processing_time_ms=processing_time,
            num_evidence=len(evidence)
        )
        
        return RAGResponse(
            answer=answer,
            evidence=evidence,
            retrieval_scores=[d["score"] for d in documents[:5]],
            avg_relevance=avg_relevance,
            processing_time_ms=processing_time,
            gate2_passed=True,
            gate2_details={
                "max_similarity": max(d["score"] for d in documents) if documents else 0,
                "relevant_count": len(reranked_docs),
            }
        )
```

---

## 7. 프롬프트 템플릿

프롬프트 설계가 답변 품질을 결정합니다.

```python
"""
프롬프트 템플릿
파일: src/rag/prompts.py
"""

# 암 연구 어시스턴트용 시스템 프롬프트
SYSTEM_PROMPT_KO = """당신은 암 연구 전문 AI 어시스턴트입니다.

역할: 제공된 연구 논문만을 기반으로 암 과학, 치료법, 예후에 관한 질문에 답변합니다.

핵심 원칙:
1. 근거 기반: 모든 주장은 제공된 논문으로 뒷받침되어야 함
2. 인용 필수: [1], [2] 등으로 출처를 인라인 표기
3. 정직한 불확실성: 논문에 없는 내용은 "제공된 논문에서 확인할 수 없습니다"라고 답변
4. 환각 금지: 사실, 통계, 인용을 만들어내지 않음
5. 권유 금지: 임상적 결정이나 치료 권고 제공 안 함

작성 스타일:
- 학술적이지만 이해하기 쉽게
- 복잡한 용어는 간단히 설명 추가
- 논문들이 다르게 말하면 여러 관점 제시
- 가능하면 수치화 (인용과 함께)
"""

SYSTEM_PROMPT_EN = """You are an oncology research AI assistant.

Your role is to answer questions about cancer science, treatments, and prognosis 
based ONLY on the research papers provided to you.

Core Principles:
1. EVIDENCE-BASED: Every claim must be supported by the provided papers
2. CITATIONS: Use [1], [2], etc. to cite sources inline
3. HONEST UNCERTAINTY: Say "the provided papers don't address this" when applicable
4. NO HALLUCINATION: Never make up facts, statistics, or citations
5. NO ADVICE: Do not give clinical recommendations or treatment advice

Writing Style:
- Academic but accessible
- Use precise terminology with brief explanations for complex terms
- Present multiple perspectives if papers disagree
- Quantify claims when possible (with citations)
"""
```

---

## 8. 성공 기준 (Acceptance Criteria)

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 검색 정밀도 (Precision@5) | 수동 평가: 상위 5개 문서가 관련있는가? | ≥ 80% |
| AC-2 | 인용 정확도 | 모든 [n] 인용이 실제 논문과 일치하는가? | 100% |
| AC-3 | 답변에 인용 포함 | 모든 답변에 최소 1개 [n] 인용 | 100% |
| AC-4 | 단순 쿼리 지연시간 | 엔드-투-엔드 API 응답 시간 | < 3초 |
| AC-5 | 복잡 쿼리 지연시간 | 멀티파트 질문에 대한 응답 시간 | < 10초 |
| AC-6 | Faithfulness (RAGAS) | 답변이 검색된 정보만 사용하는가? | ≥ 0.85 |
| AC-7 | Answer Relevancy (RAGAS) | 답변이 질문을 다루는가? | ≥ 0.80 |

---

## 9. 테스트 케이스

| TC# | 쿼리 | 예상 동작 |
|-----|------|----------|
| TC-1 | "EGFR 변이란 무엇인가?" | 관련 논문의 인용과 함께 답변 반환 |
| TC-2 | "폐암에서 erlotinib vs gefitinib 효과 비교" | 여러 인용과 함께 비교 답변 |
| TC-3 | "오늘 날씨 어때?" | Gate 1 거절 (도메인 외) |
| TC-4 | "TP53 변이가 항암제 내성에 미치는 영향" | 전문적 질문도 논문 찾아서 답변 |
| TC-5 | "xyz123 qwerty" (의미없는 입력) | Gate 2 거절 (관련 논문 없음) |
| TC-6 | "2024년 발표된 EGFR 폐암 연구" | 날짜 필터, 최신 논문만 반환 |

---

## 10. 예외 처리

| 예외 | 처리 방법 | 사용자 메시지 |
|------|----------|--------------|
| 관련 문서 없음 | Gate 2 거절 | "질문에 대한 관련 연구 논문을 찾지 못했습니다. 질문을 다르게 표현해 보세요." |
| Qdrant 타임아웃 | 3회 재시도 후 에러 | "검색 서비스가 일시적으로 느립니다. 다시 시도해 주세요." |
| LLM API 에러 | 2회 재시도 후 에러 | "답변 생성에 실패했습니다. 다시 시도해 주세요." |
| 임베딩 모델 에러 | 모델 재시작, 재시도 | (내부 재시도, 지속되면 사용자 메시지) |
| 낮은 검색 점수 (모두 < 0.5) | Gate 2 거절 | "일부 논문을 찾았지만 관련성이 충분하지 않습니다. 다르게 질문해 보세요." |

---

## 11. 생성할 파일 목록

이 스펙을 읽은 후, 다음 순서로 파일 생성:

### Week 2
1. `src/rag/chunker.py` - 텍스트 청킹 로직
2. `src/rag/embedder.py` - BGE-M3 임베딩 래퍼
3. `src/rag/models.py` - RAG용 Pydantic 모델

### Week 3
4. `src/rag/indexer.py` - Qdrant 인덱싱 파이프라인
5. `src/rag/retriever.py` - Hybrid search 구현
6. `src/rag/reranker.py` - Cross-encoder 리랭킹
7. `scripts/build_index.py` - 인덱싱 실행 스크립트

### Week 4
8. `src/rag/prompts.py` - 프롬프트 템플릿
9. `src/rag/generator.py` - Claude API 래퍼
10. `src/rag/pipeline.py` - 전체 파이프라인 조율
11. `tests/test_rag.py` - 유닛 및 통합 테스트

---

*F-02 & F-03 명세서 끝*
