# 암 논문 수집 서비스 구축 계획

> **목표**: OAR-9 에픽의 스파이크 결과물을 실제 서비스로 통합
>
> **위치**: 프로젝트 루트
>
> **작성일**: 2025-12-29
>
> **상태**: 계획 수립

---

## 1. 개요

### 1.1 서비스 목표

PubMed/Europe PMC에서 암 관련 논문을 자동 수집하여 RAG 시스템의 지식 베이스 구축

| 항목 | 목표 |
|------|------|
| 초기 수집 | 50,000건 |
| 최종 목표 | 100,000건+ |
| 데이터 소스 | Europe PMC (Open Access) |
| 수집 주기 | 초기적재 + 일일 증분 |

### 1.2 스파이크에서 가져올 것

| 스파이크 | 활용 내용 |
|----------|----------|
| OAR-9/tsy | 데이터 수집 전략, 검색 쿼리 |
| OAR-18/yts | Europe PMC API 클라이언트 |
| OAR-19/yts | XML 파싱, 전처리, 저장 로직 |
| OAR-20/yts | PostgreSQL 스키마 v2.5 |
| OAR-21/yts | 배치 아키텍처 설계 (Celery) |
| OAR-22/yts | Rate Limit, 재시도 로직 |
| OAR-23/yts | 중복 검출 로직 |

---

## 2. 폴더 구조

```
oaria/
├── docs/
│   ├── service-plan.md           # 이 문서
│   └── ...
│
├── infra/                         # 인프라 구성
│   ├── docker-compose.yml         # PostgreSQL + MinIO + Redis
│   ├── docker-compose.dev.yml     # 개발용 (포트 노출)
│   └── init/
│       └── 01-schema.sql          # DB 스키마 (OAR-20 v2.5)
│
├── batch/                         # Celery 배치 시스템 (Python)
│   ├── pyproject.toml
│   ├── src/
│   │   ├── __init__.py
│   │   ├── config.py              # 설정 관리
│   │   ├── celery_app.py          # Celery 앱
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── backfill.py        # 초기 적재
│   │   │   ├── incremental.py     # 증분 수집
│   │   │   └── repair.py          # 보정
│   │   ├── collectors/
│   │   │   ├── __init__.py
│   │   │   ├── europe_pmc.py      # API 클라이언트
│   │   │   └── rate_limiter.py    # Rate Limit
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── xml_parser.py      # XML 파싱
│   │   │   └── preprocess.py      # 전처리
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── database.py        # PostgreSQL
│   │   │   └── s3.py              # MinIO/S3
│   │   └── models/
│   │       ├── __init__.py
│   │       └── paper.py           # 데이터 모델
│   └── tests/
│       └── ...
│
├── admin/                         # 어드민 시스템
│   ├── backend/                   # NestJS
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   ├── app.module.ts
│   │   │   ├── search-queries/    # 검색 쿼리 관리
│   │   │   ├── batch-jobs/        # 배치 작업 모니터링
│   │   │   └── papers/            # 논문 조회
│   │   └── ...
│   │
│   └── frontend/                  # NextJS
│       ├── package.json
│       ├── src/
│       │   ├── app/
│       │   │   ├── page.tsx       # 대시보드
│       │   │   ├── queries/       # 쿼리 관리
│       │   │   ├── jobs/          # 배치 모니터링
│       │   │   └── papers/        # 논문 조회
│       │   └── components/
│       └── ...
│
└── README.md
```

---

## 3. 작업 순서

### Phase 0: 인프라 셋업

```
[목표] Docker 기반 개발 환경 구성

1. infra/ 디렉토리 생성
2. docker-compose.yml 작성
   - PostgreSQL 16
   - MinIO (S3 호환)
   - Redis (Celery 브로커)
3. DB 스키마 init 스크립트 (OAR-20 v2.5)
4. 인프라 실행 테스트
```

### Phase 1: Celery 배치 시스템

```
[목표] 논문 수집 배치 파이프라인 구축

1. batch/ 프로젝트 초기화 (uv)
2. OAR-9 스파이크 코드 이전
   - europe_pmc_client.py → collectors/europe_pmc.py
   - parser.py → parsers/xml_parser.py
   - storage.py → storage/database.py, storage/s3.py
3. Rate Limiter 구현 (OAR-22)
4. Celery 태스크 구현
   - backfill: 초기 적재
   - incremental: 증분 수집
5. collection_jobs 테이블 활용
6. 워커 실행 테스트
```

### Phase 2: 어드민 백엔드 (NestJS)

```
[목표] 배치 작업 관리 API

1. admin/backend/ 프로젝트 초기화
2. 모듈 구현
   - search-queries: 검색 쿼리 CRUD
   - batch-jobs: 작업 상태 조회, 수동 트리거
   - papers: 수집된 논문 조회
3. Redis → Celery 태스크 트리거 연동
```

### Phase 3: 어드민 프론트엔드 (NextJS)

```
[목표] 배치 관리 대시보드

1. admin/frontend/ 프로젝트 초기화
2. 페이지 구현
   - 대시보드: 수집 현황, 작업 상태
   - 쿼리 관리: 검색 쿼리 추가/수정/활성화
   - 배치 모니터링: 진행률, 로그
   - 논문 목록: 수집된 논문 조회
```

### Phase 4: 운영 준비

```
[목표] 프로덕션 배포 준비

1. Docker 이미지 빌드
2. Celery Beat 스케줄 설정
3. 모니터링 (로그, 메트릭)
4. 초기 적재 실행
```

---

## 4. 기술 스택

### 4.1 인프라

| 구성요소 | 기술 | 버전 |
|----------|------|------|
| Database | PostgreSQL | 16 |
| Object Storage | MinIO | latest |
| Message Broker | Redis | 7 |
| Container | Docker Compose | - |

### 4.2 배치 시스템

| 구성요소 | 기술 | 비고 |
|----------|------|------|
| 언어 | Python | 3.11+ |
| 패키지 관리 | uv | - |
| 태스크 큐 | Celery | Redis 브로커 |
| 스케줄러 | Celery Beat | - |
| HTTP 클라이언트 | httpx | async |
| DB 드라이버 | asyncpg | async |
| S3 클라이언트 | boto3 | - |

### 4.3 어드민

| 구성요소 | 기술 | 비고 |
|----------|------|------|
| Backend | NestJS | TypeScript |
| Frontend | NextJS 14 | App Router |
| ORM | Prisma | - |
| UI | shadcn/ui | - |

---

## 5. 데이터베이스 스키마

> 상세: `spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md`

### 5.1 수집 관련 테이블

```sql
-- 논문 메타데이터
papers (id, paper_id, pmcid, pmid, doi, title, ...)

-- 저자
paper_authors (paper_id, author_order, author_name, ...)

-- 섹션 offset
paper_sections (id, paper_id, section_name, offset_start, offset_end, ...)

-- 배치 작업 큐
collection_jobs (id, job_type, priority, query, status, checkpoint, ...)

-- 증분 수집 워터마크
watermarks (id, last_completed_at, overlap_days, ...)
```

### 5.2 어드민 관련 테이블 (추가)

```sql
-- 검색 쿼리 관리
search_queries (id, name, query, is_active, priority, ...)
```

---

## 6. Celery 배치 설계

> 상세: `spikes/OAR-21/yts/docs/batch-backfill-design.md`

### 6.1 큐 분리

| 배치 | 큐 이름 | 워커 | concurrency |
|------|---------|------|-------------|
| 초기 적재 | `backfill` | 3 | 35 |
| 증분 수집 | `incremental` | 1 | 10 |
| 보정 | `repair` | 1 | 5 |

### 6.2 태스크 흐름

```
[Backfill]
1. search_queries에서 active 쿼리 조회
2. Europe PMC Search API → 논문 목록
3. 체크포인트 저장 (페이지 단위)
4. Fulltext XML 수집 (병렬)
5. 파싱 → DB/S3 저장
6. collection_jobs 상태 업데이트

[Incremental]
1. watermarks에서 마지막 완료 시점 조회
2. 날짜 필터로 신규 논문 검색
3. 수집 → 파싱 → 저장
4. 워터마크 업데이트
```

### 6.3 Rate Limit

> 상세: `spikes/OAR-22/yts/docs/batch-architecture-design_v2.md`

```python
# 핵심 방어 레이어
1. RPS 제한 (토큰 버킷)
2. 동시성 제한 (세마포어)
3. 429 백오프 (Retry-After → 지수 백오프)
4. Circuit Breaker (연속 429 시 쿨다운)
```

---

## 7. 작업 체크리스트

### Phase 0: 인프라

- [ ] `infra/` 디렉토리 생성
- [ ] `docker-compose.yml` 작성 (PostgreSQL, MinIO, Redis)
- [ ] `init/01-schema.sql` 작성 (OAR-20 v2.5 + search_queries)
- [ ] 인프라 실행 테스트 (`docker compose up -d`)
- [ ] DB 연결 확인

### Phase 1: Celery 배치

- [ ] `batch/` 프로젝트 초기화
- [ ] `pyproject.toml` 작성
- [ ] OAR-9 스파이크 코드 이전 및 리팩토링
- [ ] Rate Limiter 구현
- [ ] Celery 앱 설정
- [ ] backfill 태스크 구현
- [ ] incremental 태스크 구현
- [ ] collection_jobs CRUD
- [ ] 워커 실행 테스트

### Phase 2: 어드민 백엔드

- [ ] `admin/backend/` NestJS 프로젝트 초기화
- [ ] Prisma 스키마 작성
- [ ] search-queries 모듈
- [ ] batch-jobs 모듈
- [ ] papers 모듈
- [ ] Celery 트리거 연동 (Redis)

### Phase 3: 어드민 프론트엔드

- [ ] `admin/frontend/` NextJS 프로젝트 초기화
- [ ] 대시보드 페이지
- [ ] 쿼리 관리 페이지
- [ ] 배치 모니터링 페이지
- [ ] 논문 목록 페이지

### Phase 4: 운영

- [ ] Docker 이미지 빌드
- [ ] Celery Beat 스케줄
- [ ] 초기 적재 실행
- [ ] 모니터링 설정

---

## 8. 포트 할당

| 서비스 | 포트 | 설명 |
|--------|------|------|
| PostgreSQL | 15432 | `oaria` 전용 |
| MinIO API | 19000 | S3 호환 |
| MinIO Console | 19001 | 웹 콘솔 |
| Redis | 16379 | Celery 브로커 |
| Admin Backend | 13000 | NestJS API |
| Admin Frontend | 13001 | NextJS |

> 포트 규칙: `1XXXX` - `oaria` 서비스 전용 대역

---

## 9. 참고 문서

| 문서 | 위치 |
|------|------|
| 데이터 수집 전략 | `spikes/OAR-9/tsy/데이터-수집-전략.md` |
| PostgreSQL 스키마 v2.5 | `spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md` |
| 배치 아키텍처 | `spikes/OAR-21/yts/docs/batch-backfill-design.md` |
| Rate Limit 설계 | `spikes/OAR-22/yts/docs/batch-architecture-design_v2.md` |
| 중복 검출 | `spikes/OAR-23/yts/docs/duplicate-detection-scenarios.md` |

---

## 10. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2025-12-29 | 초안 작성 |
