# Database Schema Overview

> **YTS (Your Tumor Scholar) 데이터베이스 스키마 문서**
>
> **Last Updated**: 2026-01-01

---

## 스키마 소유권

> **중요**: 각 테이블은 하나의 마이그레이션 도구에서만 관리됩니다.

| Owner | Migration Tool | Tables |
|-------|----------------|--------|
| **Backend (FastAPI)** | Alembic | papers, paper_*, batch_*, search_queries, watermarks, users, social_accounts, user_refresh_tokens |
| **Admin Backend (NestJS)** | TypeORM | admin_users, admin_refresh_tokens |

### 마이그레이션 원칙

1. **단일 소유권**: 각 테이블은 반드시 하나의 도구에서만 관리
2. **Alembic 우선**: 대부분의 핵심 테이블은 Backend Alembic에서 관리
3. **Admin 분리**: Admin 인증 관련 테이블만 TypeORM에서 관리
4. **infra/init 최소화**: extensions만 유지 (pg_trgm 등)

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                    YTS Database Architecture                     │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Weaviate  │       │ PostgreSQL  │       │    MinIO    │
│ (Vector DB) │       │   (RDB)     │       │  (S3-like)  │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ paper_chunks│       │ papers      │       │ 원문 XML    │
│ - dense vec │       │ users       │       │ 정규화 텍스트│
│ - metadata  │       │ batch_*     │       │             │
└─────────────┘       └─────────────┘       └─────────────┘
   벡터 검색            메타데이터              파일 스토리지
```

---

## 테이블 분류

### 구현 완료 ✅

| 분류 | 테이블 | Owner | 문서 |
|------|--------|-------|------|
| **논문** | `papers`, `paper_authors`, `paper_sections`, `paper_relations` | Alembic | [papers.md](./papers.md) |
| **인증/사용자** | `users`, `social_accounts`, `user_refresh_tokens` | Alembic | [users.md](./users.md) |
| **인증/관리자** | `admin_users`, `admin_refresh_tokens` | TypeORM | [users.md](./users.md) |
| **배치** | `search_queries`, `batch_jobs`, `batch_articles` 등 | Alembic | [batch.md](./batch.md) |
| **챗봇** | `conversations`, `messages`, `answer_logs` | Alembic | [chat.md](./chat.md) |

### 미구현 (예정) 📋

| 분류 | 테이블 | 용도 | 구현 시점 |
|------|--------|------|----------|
| **피드백** | `feedbacks` | 사용자 피드백 (👍/👎) | 챗봇 고도화 |

**예정 스키마 위치**: `spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md`

---

## 연결 정보

### 로컬 개발 환경 (Docker Compose)

```bash
# PostgreSQL
Host: localhost
Port: 15432
Database: oaria
User: oaria
Password: oaria_dev_2024

# Connection String
postgresql://oaria:oaria_dev_2024@localhost:15432/oaria
```

---

## 마이그레이션

### Alembic (Backend) - Primary

대부분의 테이블은 Alembic에서 관리합니다.

```bash
cd spikes/yts/backend

# 마이그레이션 실행
uv run alembic upgrade head

# 새 마이그레이션 생성
uv run alembic revision --autogenerate -m "description"

# 마이그레이션 히스토리 확인
uv run alembic history
```

**관리 테이블**: papers, paper_*, batch_*, search_queries, watermarks, users, social_accounts, user_refresh_tokens

### TypeORM (Admin Backend)

Admin 인증 테이블만 TypeORM에서 관리합니다.

```bash
cd spikes/yts/admin/backend

# 마이그레이션 실행
npm run migration:run

# 새 마이그레이션 생성
npm run migration:generate -- src/migrations/Description
```

**관리 테이블**: admin_users, admin_refresh_tokens

### Docker Init Scripts (Minimal)

PostgreSQL extensions만 초기화합니다. 테이블 생성은 Alembic/TypeORM에서 담당.

```
infra/init/
└── 00-extensions.sql    # pg_trgm 등 extensions만
```

> **주의**: 테이블 생성 SQL은 더 이상 infra/init에 두지 않습니다.

---

## ER 다이어그램

```
                    ┌─────────────────┐
                    │   admin_users   │
                    ├─────────────────┤
                    │ id (PK)         │
                    │ email           │
                    │ google_id       │
                    │ role            │
                    └────────┬────────┘
                             │ 1:N
                             ▼
                    ┌─────────────────────┐
                    │ admin_refresh_tokens│
                    └─────────────────────┘

┌─────────────────┐       ┌──────────────────┐
│     users       │       │  search_queries  │
├─────────────────┤       ├──────────────────┤
│ id (PK)         │       │ id (PK)          │
│ email           │       │ name             │
│ name            │       │ query            │
│ ...             │       │ ...              │
└────────┬────────┘       └────────┬─────────┘
         │                         │
    ┌────┴────┬────────┐           │ 1:N
    │ 1:N     │ 1:N    │ 1:N       ▼
    ▼         ▼        ▼  ┌──────────────────┐
┌─────────────┐        │  │   batch_jobs     │
│   social_   │        │  ├──────────────────┤
│  accounts   │        │  │ id (PK)          │
└─────────────┘        │  │ query_id (FK)    │
┌─────────────┐        │  │ status           │
│user_refresh_│        │  └────────┬─────────┘
│   tokens    │        │           │ 1:N
└─────────────┘        │      ┌────┴────┐
                       │      ▼         ▼
┌─────────────────┐    │ ┌──────────────┐  ┌─────────────┐
│     papers      │    │ │batch_articles│  │batch_errors │
├─────────────────┤    │ └──────────────┘  └─────────────┘
│ id (PK)         │    │ ┌──────────────┐  ┌──────────────────┐
│ paper_id        │    │ │ batch_logs   │  │batch_failed_items│
│ title           │    │ └──────────────┘  └──────────────────┘
└────────┬────────┘    │
         │             │
         │ 1:N         ▼
    ┌────┴────┐   ┌─────────────────┐
    ▼         ▼   │  conversations  │──1:N──▶ messages
┌─────────────┐   ├─────────────────┤              │
│paper_authors│   │ user_id (FK)    │              │ 1:1
└─────────────┘   │ title           │              ▼
┌─────────────┐   └────────┬────────┘        ┌─────────────┐
│paper_sections│          │ 1:N              │ answer_logs │
└─────────────┘           ▼                  │ (감사/재현) │
                    ┌─────────────┐          └─────────────┘
                    │ answer_logs │
                    └─────────────┘
```

---

## 미구현 테이블 (향후 예정)

> 피드백 기능 구현 시 추가

```
┌─────────────────┐
│   answer_logs   │──1:N──▶ feedbacks (👍/👎 피드백)
└─────────────────┘
```

---

## 관련 문서

- [papers.md](./papers.md) - 논문 관련 테이블
- [users.md](./users.md) - 사용자/인증 관련 테이블
- [batch.md](./batch.md) - 배치 작업 관련 테이블
- [chat.md](./chat.md) - 챗봇/RAG 관련 테이블
