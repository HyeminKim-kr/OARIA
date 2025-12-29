# OARIA - Cancer Paper Collection Service

암 연구 논문 자동 수집 및 관리 시스템

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Admin UI (NextJS)                     │
│                       http://localhost:13001                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Admin API (NestJS)                       │
│                    http://localhost:13000                    │
│                  Swagger: /api                               │
└─────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  PostgreSQL │      │    Redis    │      │    MinIO    │
│    :15432   │      │   :16379    │      │   :19000    │
└─────────────┘      └─────────────┘      └─────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │     Celery Worker       │
              │   (Batch Processing)    │
              └─────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │     Europe PMC API      │
              │  (Paper Collection)     │
              └─────────────────────────┘
```

## 빠른 시작

### 1. 인프라 시작
```bash
cd infra && docker-compose up -d
```

### 2. 백엔드 시작
```bash
cd admin/backend
npm install
npm run build
node dist/main.js
```

### 3. 프론트엔드 시작
```bash
cd admin/frontend
npm install
npm run build
npm run start
```

### 4. Celery Worker 시작 (논문 수집용)
```bash
cd batch
pip install -e .
celery -A src.celery_app worker -l info -Q backfill
```

## 서비스 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| Admin UI | http://localhost:13001 | 관리 대시보드 |
| Admin API | http://localhost:13000 | REST API |
| Swagger | http://localhost:13000/api | API 문서 |
| MinIO Console | http://localhost:19001 | 객체 스토리지 관리 |

## 프로젝트 구조

```
yts/
├── infra/                    # Docker 인프라
│   ├── docker-compose.yml
│   └── init.sql              # DB 스키마
├── batch/                    # Celery 배치 시스템
│   ├── src/
│   │   ├── celery_app.py     # Celery 설정
│   │   ├── collectors/       # API 클라이언트
│   │   ├── parsers/          # XML 파서
│   │   ├── storage/          # DB/S3 저장
│   │   └── tasks/            # Celery 태스크
│   └── scripts/
├── admin/
│   ├── backend/              # NestJS API
│   │   ├── src/
│   │   │   ├── entities/     # TypeORM 엔티티
│   │   │   └── modules/      # API 모듈
│   │   └── package.json
│   └── frontend/             # NextJS UI
│       ├── src/
│       │   ├── app/          # 페이지
│       │   ├── components/   # 컴포넌트
│       │   └── lib/          # 유틸리티
│       └── package.json
└── scripts/                  # 운영 스크립트
    ├── start-all.sh
    └── stop-all.sh
```

## 주요 기능

### Admin UI
- **Dashboard**: 수집 현황 개요
- **Search Queries**: 검색 쿼리 관리 (CRUD)
- **Collection Jobs**: 수집 작업 모니터링
- **Papers**: 수집된 논문 목록

### Batch System
- **Backfill**: 초기 대량 수집
- **Rate Limiting**: Token Bucket + Circuit Breaker
- **Checkpoint**: 중단점 복구 지원

## 환경 변수

### Backend (.env)
```env
DB_HOST=localhost
DB_PORT=15432
DB_USERNAME=oaria
DB_PASSWORD=oaria_dev_2024
DB_DATABASE=oaria
REDIS_URL=redis://localhost:16379
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:13000
```

## 라이선스

Internal Use Only
