# Backend: 논문 검색 및 온디맨드 수집 플로우

## 개요

사용자가 프론트엔드에서 논문을 검색할 때, Europe PMC API를 통해 실시간으로 검색 결과를 제공하고,
상세 페이지 진입 시 우리 DB에 없는 논문은 자동으로 수집하는 온디맨드(On-Demand) 수집 시스템.

---

## 플로우 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Search Papers 플로우                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

[사용자] ─── "cancer immunotherapy" 검색 ───▶ [Frontend]
                                                   │
                                                   ▼
                                            [FastAPI Backend]
                                                   │
                                                   │ Europe PMC Search API 호출
                                                   ▼
                                            [Europe PMC API]
                                                   │
                                                   │ 검색 결과 (title, abstract, pmcid, pmid, doi...)
                                                   ▼
                                            [FastAPI Backend]
                                                   │
                                                   │ 결과 변환 및 반환
                                                   ▼
                                              [Frontend]
                                                   │
                                                   │ 논문 목록 표시
                                                   ▼
                                              [사용자]


┌─────────────────────────────────────────────────────────────────────────────────┐
│                           논문 상세 페이지 진입 플로우                              │
└─────────────────────────────────────────────────────────────────────────────────┘

[사용자] ─── 논문 클릭 (PMC12345678) ───▶ [Frontend]
                                              │
                                              ▼
                                       [FastAPI Backend]
                                              │
                                              │ DB에서 논문 조회
                                              ▼
                                    ┌─────────────────────┐
                                    │   DB에 존재하는가?    │
                                    └─────────┬───────────┘
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        │ YES                 │                     │ NO
                        ▼                     │                     ▼
                ┌───────────────┐             │             ┌───────────────────┐
                │ DB에서 조회    │             │             │ Europe PMC에서     │
                │ (메타 + 본문)  │             │             │ 메타데이터 가져오기  │
                └───────┬───────┘             │             └─────────┬─────────┘
                        │                     │                       │
                        │                     │                       ▼
                        │                     │             ┌───────────────────┐
                        │                     │             │ DB에 메타데이터     │
                        │                     │             │ 저장 (papers)      │
                        │                     │             └─────────┬─────────┘
                        │                     │                       │
                        │                     │                       ▼
                        │                     │             ┌───────────────────┐
                        │                     │             │ Fulltext 수집 작업  │
                        │                     │             │ 큐에 등록           │
                        │                     │             │ (Background Task)  │
                        │                     │             └─────────┬─────────┘
                        │                     │                       │
                        ▼                     │                       ▼
                ┌───────────────────────────────────────────────────────────────┐
                │                        응답 반환                                │
                │  - 메타데이터 (title, abstract, authors, journal, year...)     │
                │  - fulltext_status: "available" | "processing" | "pending"    │
                │  - fulltext: 본문 텍스트 (있는 경우)                             │
                └───────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                                         [Frontend]
                                              │
                                              │ 상세 페이지 표시
                                              │ (본문 없으면 "본문 준비 중..." 표시)
                                              ▼
                                          [사용자]


┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Background Fulltext 수집 플로우                          │
└─────────────────────────────────────────────────────────────────────────────────┘

[FastAPI] ─── Celery Task 등록 ───▶ [Redis Queue]
                                         │
                                         │ celery-worker-ondemand (새 워커)
                                         ▼
                                   [Celery Worker]
                                         │
                                         ├── 1. Europe PMC Fulltext API 호출
                                         │       └── XML 다운로드
                                         │
                                         ├── 2. XML 파싱
                                         │       └── fulltext.txt 추출
                                         │       └── sections offset 추출
                                         │
                                         ├── 3. S3 저장
                                         │       └── {bucket}/{prefix}/fulltext.txt
                                         │       └── {bucket}/{prefix}/raw.xml
                                         │
                                         ├── 4. DB 업데이트
                                         │       └── papers.canonical_prefix 설정
                                         │       └── papers.status = 'collected'
                                         │       └── paper_sections 저장
                                         │
                                         └── 5. 임베딩 작업 큐 등록 (기존 embed 워커)
                                                 └── Queue: embed
```

---

## API 설계

### 1. 논문 검색 (Europe PMC 프록시)

```
GET /papers/search/europe-pmc
```

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| q | string | Yes | 검색어 |
| page | int | No | 페이지 (default: 1) |
| limit | int | No | 페이지당 결과 수 (default: 20, max: 100) |
| year_from | int | No | 시작 연도 |
| year_to | int | No | 종료 연도 |
| open_access | bool | No | Open Access만 (default: true) |

**Response:**
```json
{
  "items": [
    {
      "pmcid": "PMC12345678",
      "pmid": "12345678",
      "doi": "10.1234/example",
      "title": "Cancer Immunotherapy...",
      "abstract": "This study investigates...",
      "journal": "Nature Medicine",
      "year": 2024,
      "authors": ["Kim J", "Lee S", "Park M"],
      "is_open_access": true,
      "source": "europe_pmc",
      "in_our_db": true  // 우리 DB에 있는지 여부
    }
  ],
  "total": 1234,
  "page": 1,
  "limit": 20,
  "total_pages": 62
}
```

### 2. 논문 상세 조회 (온디맨드 수집 포함)

```
GET /papers/{pmcid}
```

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| pmcid | string | PMC ID (예: PMC12345678) |

**Response:**
```json
{
  "id": "uuid (우리 DB ID, 없으면 null)",
  "pmcid": "PMC12345678",
  "pmid": "12345678",
  "doi": "10.1234/example",
  "title": "Cancer Immunotherapy...",
  "abstract": "This study investigates...",
  "journal": "Nature Medicine",
  "year": 2024,
  "keywords": ["cancer", "immunotherapy"],
  "authors": [
    {
      "author_name": "Kim J",
      "author_order": 1,
      "is_corresponding": true,
      "affiliation": "Seoul National University"
    }
  ],
  "fulltext_status": "available" | "processing" | "pending",
  "fulltext": "Full text content here... (available일 때만)",
  "source_url": "https://europepmc.org/article/PMC/12345678"
}
```

**동작:**
1. `pmcid`로 우리 DB 조회
2. **DB에 있고 fulltext 있음** → 바로 반환
3. **DB에 있지만 fulltext 없음** → 메타데이터 반환 + `fulltext_status: "processing"`
4. **DB에 없음** → Europe PMC에서 메타데이터 가져와서 DB 저장 + Background Task 등록 + 반환

### 3. Fulltext 상태 확인 (폴링용)

```
GET /papers/{pmcid}/status
```

**Response:**
```json
{
  "pmcid": "PMC12345678",
  "fulltext_status": "available" | "processing" | "pending" | "failed",
  "error_message": "Failed to download..." // failed일 때만
}
```

---

## DB 스키마 변경

### papers 테이블 컬럼 추가

```sql
ALTER TABLE papers ADD COLUMN IF NOT EXISTS fulltext_status VARCHAR(20) DEFAULT 'pending';
-- pending: 아직 수집 안됨
-- processing: 수집 중
-- available: 수집 완료
-- failed: 수집 실패

ALTER TABLE papers ADD COLUMN IF NOT EXISTS fulltext_error TEXT;
-- 실패 시 에러 메시지
```

---

## Celery Task 설계

### 새 큐: `ondemand`

기존 `backfill` 큐와 분리하여 온디맨드 요청을 빠르게 처리.

```python
# batch/src/celery_app.py
app.conf.task_routes = {
    'tasks.backfill.*': {'queue': 'backfill'},
    'tasks.embed.*': {'queue': 'embed'},
    'tasks.ondemand.*': {'queue': 'ondemand'},  # 새 큐
}
```

### Task: `fetch_paper_fulltext`

```python
@celery_app.task(queue='ondemand', bind=True, max_retries=3)
def fetch_paper_fulltext(self, pmcid: str):
    """
    온디맨드 논문 본문 수집

    1. Europe PMC Fulltext API 호출
    2. XML 파싱 → fulltext.txt 추출
    3. S3 저장
    4. DB 업데이트 (papers, paper_sections)
    5. 임베딩 작업 등록
    """
    try:
        # 상태 업데이트: processing
        update_paper_status(pmcid, 'processing')

        # Fulltext 수집 로직 (기존 backfill 로직 재사용)
        xml = download_fulltext_xml(pmcid)
        parsed = parse_xml(xml)

        # S3 저장
        save_to_s3(pmcid, parsed.fulltext, xml)

        # DB 업데이트
        update_paper_fulltext(pmcid, parsed)

        # 임베딩 작업 등록
        embed_paper.delay(pmcid)

        # 상태 업데이트: available
        update_paper_status(pmcid, 'available')

    except Exception as e:
        update_paper_status(pmcid, 'failed', str(e))
        raise self.retry(exc=e, countdown=60)
```

---

## 워커 구성 (docker-compose 추가)

```yaml
celery-worker-ondemand:
  build:
    context: ./batch
  command: celery -A src.celery_app worker -Q ondemand -c 4 --loglevel=info
  environment:
    - CELERY_BROKER_URL=redis://redis:6379/0
  depends_on:
    - redis
    - postgres
```

**설정:**
- Queue: `ondemand`
- Concurrency: 4 (빠른 응답 위해)
- 기존 `backfill` (c=2), `embed` (c=1)와 분리

---

## 프론트엔드 연동

### Search Papers 모드

```typescript
// 검색 시
const results = await api.get('/papers/search/europe-pmc', {
  params: { q: query, page, limit }
});

// 결과 표시 (Europe PMC 데이터 직접 사용)
results.items.map(paper => <PaperCard paper={paper} />);
```

### 상세 페이지

```typescript
// 상세 페이지 진입
const paper = await api.get(`/papers/${pmcid}`);

// fulltext_status에 따른 UI
if (paper.fulltext_status === 'available') {
  // 본문 표시
} else if (paper.fulltext_status === 'processing') {
  // "본문 준비 중..." + 폴링
  pollStatus(pmcid);
} else {
  // "본문을 가져오는 중..."
}
```

---

## 구현 우선순위

1. **Phase 1: Europe PMC 검색 프록시 API**
   - `/papers/search/europe-pmc` 엔드포인트
   - Europe PMC Search API 호출 로직

2. **Phase 2: 온디맨드 상세 조회**
   - `/papers/{pmcid}` 엔드포인트
   - DB 조회 → 없으면 Europe PMC에서 메타데이터 가져오기

3. **Phase 3: Background Fulltext 수집**
   - Celery `ondemand` 큐 설정
   - `fetch_paper_fulltext` Task 구현
   - 기존 backfill 로직 재사용

4. **Phase 4: 프론트엔드 연동**
   - Search Papers UI 연결
   - 상세 페이지 + 폴링

---

## 참고: 기존 Batch 시스템과의 관계

```
┌─────────────────────────────────────────────────────────────────┐
│                     논문 수집 경로                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Admin Backfill (대량 수집)                                   │
│     └── Admin UI → NestJS → Celery backfill 큐                  │
│         └── 검색 쿼리 기반 대량 수집                              │
│         └── rate limiting, checkpoint 등                         │
│                                                                  │
│  2. On-Demand (사용자 요청)           ← 이번에 구현               │
│     └── User Frontend → FastAPI → Celery ondemand 큐            │
│         └── 개별 논문 빠른 수집                                   │
│         └── 사용자 경험 우선                                      │
│                                                                  │
│  3. Embedding (공통)                                             │
│     └── 두 경로 모두 → Celery embed 큐                           │
│         └── Weaviate 벡터화                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
