# Database Schema Overview

> **YTS (Your Tumor Scholar) 데이터베이스 스키마 문서**
>
> **Last Updated**: 2025-12-31

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
│ - metadata  │       │ batch jobs  │       │             │
└─────────────┘       └─────────────┘       └─────────────┘
   벡터 검색            메타데이터              파일 스토리지
```

---

## 테이블 분류

| 분류 | 테이블 | 설명 | 문서 |
|------|--------|------|------|
| **논문** | `papers`, `paper_authors`, `paper_sections` | 논문 메타데이터 및 저자, 섹션 정보 | [papers.md](./papers.md) |
| **인증/사용자** | `users`, `social_accounts`, `user_refresh_tokens` | 서비스 사용자, 소셜 로그인, JWT | [users.md](./users.md) |
| **인증/관리자** | `admin_users`, `admin_refresh_tokens` | 관리자, JWT | [users.md](./users.md) |
| **배치** | `search_queries`, `collection_jobs`, `article_jobs` 등 | 논문 수집 배치 작업 관리 | [batch.md](./batch.md) |

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

### Alembic (Backend)

```bash
cd spikes/yts/backend

# 마이그레이션 실행
uv run alembic upgrade head

# 새 마이그레이션 생성
uv run alembic revision --autogenerate -m "description"

# 마이그레이션 히스토리 확인
uv run alembic history
```

### Docker Init Scripts

`docker-compose.yml`의 PostgreSQL 컨테이너는 `./infra/init` 폴더의 SQL 파일을 초기화 시 실행합니다.

```
infra/init/
├── 01-schema.sql           # 기본 스키마 (papers, batch jobs 등)
└── 02-embedding-columns.sql # 임베딩 관련 컬럼 추가
```

> **주의**: `docker-entrypoint-initdb.d`는 볼륨이 **처음 생성될 때만** 실행됩니다.
> 기존 볼륨이 있으면 Alembic 마이그레이션을 사용하세요.

---

## ER 다이어그램

```
                    ┌─────────────────┐
                    │   admin_users   │
                    ├─────────────────┤
                    │ id (PK)         │
                    │ email           │
                    │ password_hash   │
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
    ┌────┴────┐                    │ 1:N
    │ 1:N     │ 1:N                ▼
    ▼         ▼           ┌──────────────────┐
┌─────────────┐           │ collection_jobs  │
│   social_   │           ├──────────────────┤
│  accounts   │           │ id (PK)          │
└─────────────┘           │ query_id (FK)    │
┌─────────────┐           │ status           │
│user_refresh_│           └────────┬─────────┘
│   tokens    │                    │ 1:N
└─────────────┘                    ▼
                          ┌──────────────────┐
┌─────────────────┐       │   article_jobs   │
│     papers      │       └──────────────────┘
├─────────────────┤
│ id (PK)         │
│ paper_id        │
│ title           │
└────────┬────────┘
         │
         │ 1:N
    ┌────┴────┐
    ▼         ▼
┌─────────────┐  ┌───────────────┐
│paper_authors│  │paper_sections │
└─────────────┘  └───────────────┘
```

---

## 관련 문서

- [papers.md](./papers.md) - 논문 관련 테이블
- [users.md](./users.md) - 사용자/인증 관련 테이블
- [batch.md](./batch.md) - 배치 작업 관련 테이블
