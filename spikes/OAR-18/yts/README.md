# OAR-18: Europe PMC API 연동

> **담당**: yts
>
> **목적**: 암 논문 수집을 위한 Europe PMC API 클라이언트 구현

---

## 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| **데이터 소스** | Europe PMC | 전문(Full-text) 무료 제공 |
| **수집 대상** | Open Access만 | 합법적 전문 수집 |
| **검색 쿼리** | `neoplasms AND OPEN_ACCESS:Y` | MeSH 표준 용어 |

> ⚠️ 태스크 제목은 "PubMed API"이지만, **Europe PMC API**로 구현

---

## 아키텍처

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   viewer.html   │ ──► │  FastAPI 서버   │ ──► │   Europe PMC    │
│   (브라우저)     │     │  (Python)       │     │   REST API      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     :8081                   :8000              europepmc.org
```

- **viewer.html**: 팀 피드백용 데모 UI
- **FastAPI 서버**: Python 백엔드 (검색, 전문 수집)
- **Europe PMC**: 실제 데이터 소스

---

## 폴더 구조

```
OAR-18/yts/
├── README.md                    # 이 문서
├── pyproject.toml               # 프로젝트 설정
├── src/
│   ├── __init__.py
│   ├── europe_pmc_client.py     # API 클라이언트
│   └── server.py                # FastAPI 서버
├── samples/
│   └── viewer.html              # 팀 피드백용 데모 화면
└── docs/
    └── api-guide.md             # API 사용 가이드 (예정)
```

---

## 빠른 시작

### 1. 환경 설정

```bash
cd spikes/OAR-18/yts
uv sync  # 의존성 설치
```

### 2. 데모 실행 (통합 테스트)

**터미널 1: FastAPI 백엔드**
```bash
cd spikes/OAR-18/yts
uv run uvicorn src.server:app --reload --port 8000
```

**터미널 2: 데모 화면**
```bash
cd spikes/OAR-18/yts/samples
python3 -m http.server 8081
# → http://localhost:8081/viewer.html
```

### 3. CLI 사용법

```bash
# 메타데이터 검색 (초록만)
uv run python -m src.europe_pmc_client search "lung cancer" --limit 10

# 전문 포함 검색 (Open Access만)
uv run python -m src.europe_pmc_client fulltext "breast cancer" --limit 5

# JSON 저장
uv run python -m src.europe_pmc_client fulltext "neoplasms" -l 10 --save
```

### 4. Python에서 직접 사용

```python
from src.europe_pmc_client import EuropePMCClient

client = EuropePMCClient()

# 메타데이터 검색
result = client.search("neoplasms", limit=10)
for paper in result['papers']:
    print(f"[{paper.pmcid}] {paper.title}")

# 전문 포함 수집
papers = client.search_with_fulltext("lung cancer", limit=5)
for paper in papers:
    if paper.full_text:
        print(f"전문 길이: {len(paper.full_text)} chars")
        print(f"섹션: {list(paper.full_text_sections.keys())}")
```

---

## API 엔드포인트

### 검색 API

```
GET https://www.ebi.ac.uk/europepmc/webservices/rest/search
```

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `query` | 검색 쿼리 | `neoplasms AND OPEN_ACCESS:Y` |
| `format` | 응답 형식 | `json` |
| `pageSize` | 결과 수 | `25` (max 1000) |
| `cursorMark` | 페이지네이션 | `*` (첫 페이지) |

### 전문 조회 API

```
GET https://www.ebi.ac.uk/europepmc/webservices/rest/{source}/{id}/fullTextXML
```

---

## 진행 상황

- [x] API 클라이언트 기본 구조
- [x] 검색 기능 구현
- [x] 전문(Full-text) 조회 구현
- [x] FastAPI 백엔드 서버
- [x] 팀 피드백용 데모 화면 (통합 아키텍처)
- [x] Rate Limit 핸들링 (기본)
- [ ] 비동기 처리 (aiohttp)

---

## 참고 자료

- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [Europe PMC API 문서](https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf)
- [OAR-9 데이터 수집 전략](../../OAR-9/tsy/데이터-수집-전략.md)
