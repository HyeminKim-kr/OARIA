# OAR-9 데모 완성 작업 플랜

> **목표**: OAR-9 에픽의 모든 하위 태스크(OAR-18~23)를 통합하여 완전한 논문 수집 파이프라인 데모 완성
>
> **작성일**: 2025-12-29
>
> **상태**: 진행 중

---

## 1. 현재 상태

### 1.1 완료된 항목

| 구분 | 태스크 | 내용 | 상태 |
|------|--------|------|------|
| **스키마** | OAR-20 | PostgreSQL v2.5 스키마 적용 | ✅ 완료 |
| **인프라** | - | Docker Compose (PostgreSQL + MinIO) | ✅ 완료 |
| **API 클라이언트** | OAR-18 | AsyncEuropePMCClient (검색, XML 수집) | ✅ 통합 |
| **파싱 로직** | OAR-19 | PaperParser, models, preprocess | ✅ 통합 |
| **저장 로직** | OAR-19/20 | DatabaseStorage + S3Storage | ✅ 완료 |
| **파이프라인** | - | 검색 → 수집 → 파싱 → 저장 | ✅ 완료 |
| **데모 UI** | - | Streamlit 3탭 (검색/목록/상세) | ✅ 완료 |

### 1.2 미완료 항목

| 구분 | 태스크 | 내용 | 우선순위 |
|------|--------|------|----------|
| **Rate Limit** | OAR-22 | 429/5xx 재시도, Circuit Breaker | P0 (MVP 필수) |
| **배치 시스템** | OAR-21 | Celery 태스크 (초기적재/증분/보정) | P1 |
| **중복 검출** | OAR-23 | 중복 논문 검출 로직 | P2 |
| **인프라** | - | Redis 추가 (Celery용) | P1 |
| **작업 큐** | OAR-21 | collection_jobs 테이블 활용 | P1 |
| **워터마크** | OAR-21 | watermarks 테이블 활용 (증분 수집) | P1 |

### 1.3 수정 필요 항목

| 파일 | 문제 | 해결 방안 |
|------|------|----------|
| `demo_app.py` | 사이드바 기본값이 config.py와 불일치 | 포트/비밀번호 통일 |

---

## 2. 작업 계획

### Phase 1: 기본 정리 (즉시)

#### 1.1 데모 앱 설정 수정

**파일**: `demo_app.py`

```python
# 변경 전
db_port = st.number_input("Port", value=5432, ...)
db_password = st.text_input("Password", value="oaria123", ...)
s3_endpoint = st.text_input("Endpoint", value="http://localhost:9000")

# 변경 후 (config.py와 일치)
db_port = st.number_input("Port", value=10932, ...)  # OAR-9 고유 포트
db_password = st.text_input("Password", value="oaria_dev", ...)
s3_endpoint = st.text_input("Endpoint", value="http://localhost:10900")
```

#### 1.2 데모 실행 테스트

```bash
# 1. 인프라 시작
cd spikes/OAR-9/yts
docker compose -f docker/docker-compose.yml up -d

# 2. 의존성 설치
uv sync

# 3. 데모 실행
uv run streamlit run demo_app.py
```

---

### Phase 2: Rate Limit 구현 (MVP 필수)

> **참고 문서**: `spikes/OAR-22/yts/docs/rate-limit-retry-design.md`

#### 2.1 새 파일 추가

**파일**: `src/rate_limiter.py`

```python
# 구현 항목:
# 1. APILimiter: 토큰 버킷 + 세마포어
# 2. 429 처리: Retry-After 우선, 지수 백오프 + 지터
# 3. 5xx/timeout 처리: 백오프 재시도
# 4. Circuit Breaker: 연속 429 시 쿨다운
```

#### 2.2 API 클라이언트 수정

**파일**: `src/europe_pmc_client.py`

- `rate_limiter.py`의 `RequestManager` 통합
- 기존 단순 delay → 지능적 rate limiting으로 교체

#### 2.3 테스트

```python
# 429 시뮬레이션 테스트
# Circuit Breaker 동작 확인
# 대량 수집 시 안정성 검증
```

---

### Phase 3: 배치 시스템 구현

> **참고 문서**: `spikes/OAR-21/yts/docs/batch-backfill-design.md`

#### 3.1 인프라 추가

**파일**: `docker/docker-compose.yml`

```yaml
services:
  # 기존 postgres, minio 유지

  redis:
    image: redis:7-alpine
    container_name: oar9-redis
    ports:
      - "10979:6379"  # 09 + 79 (from 6379)
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
```

#### 3.2 Celery 구조

**새 파일들**:
```
src/
├── batch/
│   ├── __init__.py
│   ├── celery_app.py      # Celery 앱 설정
│   ├── tasks.py           # 태스크 정의
│   └── worker.py          # 워커 진입점
```

#### 3.3 태스크 정의

```python
# batch/tasks.py

@app.task(queue='backfill')
def backfill(query_id: str):
    """초기 적재 배치"""
    ...

@app.task(queue='incremental')
def incremental():
    """증분 수집 (매일)"""
    ...

@app.task(queue='repair')
def repair():
    """보정 배치 (주 1회)"""
    ...
```

#### 3.4 collection_jobs 활용

```python
# 작업 생성
INSERT INTO collection_jobs (job_type, priority, query, ...) VALUES (...)

# 작업 획득 (SKIP LOCKED)
UPDATE collection_jobs SET status='running', locked_by=$1
WHERE id = (SELECT id FROM collection_jobs WHERE status='pending' ... FOR UPDATE SKIP LOCKED)

# 체크포인트 저장
UPDATE collection_jobs SET checkpoint=$1 WHERE id=$2
```

---

### Phase 4: 중복 검출 (선택)

> **참고 문서**: `spikes/OAR-23/yts/docs/duplicate-detection-scenarios.md`

#### 4.1 구현 범위

- DOI/PMID/PMCID 기반 중복 체크 (이미 DB 인덱스로 처리됨)
- 제목 유사도 기반 중복 검출 (향후)

---

## 3. 파일 구조 (최종)

```
spikes/OAR-9/yts/
├── README.md
├── pyproject.toml
├── demo_app.py                    # Streamlit 데모
├── docker/
│   ├── docker-compose.yml         # PostgreSQL + MinIO + Redis
│   └── init/
│       └── 01-schema.sql          # OAR-20 v2.5 스키마
├── docs/
│   └── work-plan.md               # 이 문서
├── src/
│   ├── __init__.py
│   ├── config.py                  # 설정 관리
│   ├── models.py                  # 데이터 모델
│   ├── europe_pmc_client.py       # API 클라이언트
│   ├── parser.py                  # XML 파싱
│   ├── preprocess.py              # 텍스트 전처리
│   ├── storage.py                 # DB/S3 저장
│   ├── pipeline.py                # 통합 파이프라인
│   ├── rate_limiter.py            # [Phase 2] Rate Limit
│   └── batch/                     # [Phase 3] 배치 시스템
│       ├── __init__.py
│       ├── celery_app.py
│       ├── tasks.py
│       └── worker.py
└── tests/
    └── ...
```

---

## 4. 작업 체크리스트

### Phase 1: 기본 정리
- [ ] `demo_app.py` 사이드바 기본값 수정
- [ ] Docker Compose 실행 테스트
- [ ] Streamlit 데모 실행 테스트
- [ ] 논문 검색 → 수집 → 저장 E2E 테스트

### Phase 2: Rate Limit
- [ ] `src/rate_limiter.py` 생성
- [ ] `APILimiter` 클래스 구현 (토큰 버킷 + 세마포어)
- [ ] 429 재시도 로직 (Retry-After, 지수 백오프)
- [ ] 5xx/timeout 재시도 로직
- [ ] Circuit Breaker 구현
- [ ] `europe_pmc_client.py`에 통합
- [ ] 대량 수집 테스트 (100건+)

### Phase 3: 배치 시스템
- [ ] `docker-compose.yml`에 Redis 추가
- [ ] `src/batch/` 디렉토리 생성
- [ ] Celery 앱 설정 (`celery_app.py`)
- [ ] 배치 태스크 정의 (`tasks.py`)
- [ ] `collection_jobs` 테이블 활용 로직
- [ ] `watermarks` 테이블 활용 로직
- [ ] 초기 적재(Backfill) 태스크 구현
- [ ] 증분 수집(Incremental) 태스크 구현
- [ ] 워커 실행 테스트

### Phase 4: 중복 검출 (선택)
- [ ] DOI→PMID 매핑 로직
- [ ] 제목 유사도 검출 (향후)

---

## 5. 참고 문서

| 태스크 | 문서 위치 |
|--------|----------|
| OAR-9 (Epic) | `spikes/OAR-9/tsy/README.md` |
| OAR-18 (API) | `spikes/OAR-18/yts/README.md` |
| OAR-19 (파싱) | `spikes/OAR-19/yts/README.md` |
| OAR-20 (스키마) | `spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md` |
| OAR-21 (배치) | `spikes/OAR-21/yts/docs/batch-backfill-design.md` |
| OAR-22 (Rate Limit) | `spikes/OAR-22/yts/docs/batch-architecture-design_v2.md` |
| OAR-23 (중복) | `spikes/OAR-23/yts/docs/duplicate-detection-scenarios.md` |

---

## 6. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2025-12-29 | 초안 작성 |
