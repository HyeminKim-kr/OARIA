# Study Plan Agent v4 - Backend Architecture

> **작성일**: 2025-01-30
> **버전**: v4 (LangGraph 기반)

이 문서는 Study Plan Agent의 백엔드 아키텍처를 설명합니다.

---

## 목차

1. [디렉토리 구조](#디렉토리-구조)
2. [핵심 아키텍처](#핵심-아키텍처)
3. [검색 시스템](#검색-시스템)
4. [SSE 이벤트 시스템](#sse-이벤트-시스템)
5. [통합 출력 형식](#통합-출력-형식)
6. [수정 가이드](#수정-가이드)

---

## 디렉토리 구조

```
study_plan/
├── service.py              # 메인 서비스 엔트리포인트
├── shared/                 # 공용 모듈 (버전 간 공유)
│   ├── rag/               # RAG 검색 서비스
│   │   ├── search.py      # StudySearchService (Weaviate + Tavily 통합)
│   │   └── types.py       # PaperResult, SnippetResult 등
│   └── search/            # 외부 검색 서비스
│       ├── europe_pmc_service.py  # Europe PMC API
│       └── tavily_service.py      # Tavily Web Search API
│
└── v4/                     # v4 LangGraph 기반 에이전트
    ├── service.py          # StudyPlanAgentV4 메인 클래스
    │
    ├── constants/          # 상수 정의
    │   └── events.py       # AgentEventType (SSE 이벤트 타입)
    │
    ├── core/               # 핵심 컴포넌트
    │   ├── types.py        # Action, Observation 등 타입
    │   ├── reasoner.py     # Reasoner (LLM 추론)
    │   ├── executor.py     # Executor (도구 실행)
    │   └── goal_checker.py # GoalChecker (목표 달성 검사)
    │
    ├── langgraph/          # LangGraph 그래프 정의
    │   ├── graph.py        # StateGraph 빌더
    │   ├── state.py        # StudyPlanState (TypedDict)
    │   ├── streaming.py    # SSE 스트리밍 어댑터
    │   └── nodes/          # 그래프 노드들
    │       ├── execute.py  # 실행 노드 ⭐ (sources 배열 생성)
    │       └── ...
    │
    └── tools/              # 에이전트 도구들
        ├── base.py         # BaseTool 추상 클래스
        ├── registry.py     # ToolRegistry
        └── search/         # 검색 도구 ⭐
            ├── rag_tool.py     # search_rag (Weaviate + Tavily 통합)
            ├── epmc_tool.py    # search_epmc (Europe PMC)
            └── web_tool.py     # search_web (Tavily)
```

---

## 핵심 아키텍처

### LangGraph 상태 그래프

```
START → initialize → reason ←──────┐
                       ↓           │
                    execute        │
                       ↓           │
                    observe        │
                       ↓           │
                  check_goal ──────┘ (continue)
                       ↓ (done/error)
                   finalize → END
```

---

## 검색 시스템

### 검색 도구 구조

| 도구 | 소스 | paper_id 형식 | URL 처리 |
|------|------|---------------|----------|
| `search_rag` | Weaviate + Tavily | `pmc:PMC...` 또는 `web_...` | DB 조회 / journal 필드 |
| `search_epmc` | Europe PMC | `PMC...` 또는 `pmid` | 직접 생성 |
| `search_web` | Tavily | 없음 | 직접 반환 |

### RAG Search 데이터 흐름

```
┌─────────────────────────────────────────────────────────────────────┐
│ StudySearchService (shared/rag/search.py)                           │
│   ├── Weaviate 검색 → paper_id: "pmc:PMC..." (DB 조회 필요)         │
│   └── Tavily 검색 → paper_id: "web_...", URL은 journal에 저장       │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ RAGSearchTool (tools/search/rag_tool.py)                            │
│   1. Weaviate/Tavily 결과 분리 (paper_id.startswith("web_"))        │
│   2. Weaviate → _fetch_paper_urls() → DB에서 doi/pmcid/pmid 조회    │
│   3. Tavily → journal 필드에서 URL 추출, domain만 표시              │
│   4. 통합 출력 형식으로 변환                                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ execute.py (_extract_sources)                                       │
│   → SSE observation 이벤트용 sources 배열 생성                       │
│   → 프론트엔드 SourcesCard에서 사용                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### URL 우선순위

```python
# 우선순위: source_url > DOI > PMC > PubMed
if paper.source_url:
    url = paper.source_url
elif paper.doi:
    url = f"https://doi.org/{paper.doi}"
elif paper.pmcid:
    url = f"https://europepmc.org/article/PMC/{paper.pmcid}"
elif paper.pmid:
    url = f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/"
```

---

## SSE 이벤트 시스템

### 이벤트 타입

| 이벤트 | 설명 | 프론트엔드 처리 |
|--------|------|----------------|
| `initialization` | 에이전트 시작 | 초기화 UI |
| `thinking` | LLM 사고 과정 | Extended Thinking |
| `acting` | 액션 실행 중 | 로딩 상태 |
| `observation` | 액션 결과 ⭐ | Sources 카드, 상세 카드 |
| `goal_check` | 목표 검사 | 진행률 |
| `completed` | 에이전트 완료 | 결과 패널 |
| `result` | 최종 결과 | Plan A/B |

### observation 이벤트 구조

```python
{
    "event": "observation",
    "data": {
        "iteration": 3,
        "action": "search_rag",
        "success": true,
        "sources": [  # ⭐ execute.py의 _extract_sources()에서 생성
            {
                "id": 1,
                "type": "paper",
                "title": "...",
                "url": "https://doi.org/...",      # 클릭 시 이동
                "source": "rag",                   # rag | epmc | web
                "journal": "Nature",
                "year": 2024,
                "relevance": 0.85,
                "doi": "10.1038/...",
                "pmcid": "PMC12345",
                "pmid": "12345678"
            }
        ],
        "summary": "관련 논문 10편을 찾았어요! 관련도 72%",
        "details": { ... }
    }
}
```

---

## 통합 출력 형식

### 검색 도구 출력 (papers[])

모든 검색 도구는 동일한 형식으로 papers를 반환합니다:

```python
{
    # 공통 필수 필드 (모든 소스)
    "title": str,                    # 제목
    "url": str | None,               # 클릭 시 이동할 URL
    "score": float,                  # 관련도 점수 (0-1)
    "source": "rag" | "epmc" | "web",  # 검색 소스
    "citation_text": str,            # 짧은 인용 텍스트
    "markdown_link": str,            # [제목](URL) 형식

    # 논문 전용 필드 (Weaviate, EPMC)
    "paper_id": str | None,          # pmc:PMC..., pmid:..., web_...
    "journal": str | None,           # 저널명 (Tavily: 도메인)
    "year": int | None,              # 발행연도
    "doi": str | None,
    "pmcid": str | None,
    "pmid": str | None,

    # Web 전용 필드 (Tavily)
    "content": str | None,           # 웹 페이지 내용
}
```

### source 값 기준

| source | 설명 | paper_id 형식 |
|--------|------|---------------|
| `"rag"` | Weaviate (내부 DB) | `pmc:PMC...` 또는 `pmid:...` |
| `"epmc"` | Europe PMC | `PMC...` 또는 PMID |
| `"web"` | Tavily 웹 검색 | `web_...` (UUID) |

---

## 수정 가이드

### 검색 도구 수정 시

1. **출력 형식 유지**: 위의 통합 출력 형식을 따를 것
2. **source 필드 필수**: `"rag"`, `"epmc"`, `"web"` 중 하나
3. **URL 필드 필수**: 클릭 가능하도록 URL 반환

### 새 검색 소스 추가 시

1. `tools/search/`에 새 도구 파일 생성
2. `BaseTool` 상속, 통합 출력 형식 반환
3. `tools/registry.py`에 등록
4. `execute.py`의 `_extract_sources()`에 새 source 타입 추가:

```python
source_type_map = {
    "search_rag": "rag",
    "search_epmc": "epmc",
    "search_web": "web",
    "search_new": "new",  # 새 소스 추가
}
```

5. 프론트엔드 타입 및 뱃지 업데이트 (아래 문서 참고)

### execute.py 수정 시

`_extract_sources()` 함수가 SSE 이벤트의 sources 배열을 생성합니다.
새 필드 추가 시 이 함수도 업데이트해야 합니다.

---

## 관련 문서

- **프론트엔드 문서**: `frontend/src/app/agents/study-plan/README.md`
- **프로젝트 규칙**: `CLAUDE.md`

---

## 디버깅 팁

### 로그 확인

```python
# RAG 검색 결과 로그
logger.info(f"Search results: {len(weaviate_papers)} from Weaviate, ...")

# DB 조회 실패 로그 (debug 레벨)
logger.debug(f"Papers not found in DB: {list(missing)[:3]}...")
```

### Docker 로그

```bash
docker logs oaria-service-backend-dev --tail=100 | grep "search_rag"
```
