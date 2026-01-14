# OARIA 개발 스크립트

개발 환경 관리 및 Git 워크플로우 자동화 스크립트입니다.

---

## Git Commit Workflow

인터랙티브하게 스테이징, 커밋, 머지까지 한 번에 처리합니다.

```bash
./scripts/git-commit.sh
```

### 워크플로우 순서

1. **브랜치 확인** - 현재 브랜치가 맞는지, 새 브랜치 생성 옵션
2. **파일 스테이징** - 전체/개별 선택 가능
3. **Jira 티켓** - 브랜치에서 자동 감지 또는 직접 입력
4. **커밋 메시지** - 타입(feat/fix/...) + 스코프 + 메시지
5. **dev 머지** - git-merge.sh 자동 실행 (선택)

### 옵션

```bash
./scripts/git-commit.sh --no-merge   # 커밋만 하고 머지 안함
```

### 커밋 메시지 형식

```
feat(admin): 사용자 관리 기능 추가

OAR-123
```

---

## 개발 환경 관리 (dev.sh)

### 빠른 시작

```bash
# 모든 서비스 시작
./scripts/dev.sh start

# 상태 확인
./scripts/dev.sh status
```

### 명령어

| 명령어 | 설명 |
|--------|------|
| `start` | 모든 서비스 시작 (Docker → Admin → Service) |
| `stop` | 모든 서비스 중지 |
| `restart` | 모든 서비스 재시작 |
| `status` | 서비스 상태 및 URL 확인 |
| `monitor` | 실시간 모니터링 (5초마다 갱신) |
| `logs` | 로그 보기 (선택 메뉴) |

### 개별 서비스 제어

```bash
# Docker (인프라 + Celery)
./scripts/dev.sh docker start
./scripts/dev.sh docker stop

# Admin (Backend + Frontend)
./scripts/dev.sh admin start
./scripts/dev.sh admin stop

# User Service (Backend + Frontend)
./scripts/dev.sh service start
./scripts/dev.sh service stop
```

### 서비스 구성

#### Docker Compose (인프라)

| 서비스 | 포트 | 설명 |
|--------|------|------|
| PostgreSQL | 15432 | 메인 데이터베이스 |
| Redis | 16379 | 캐시 및 Celery 브로커 |
| MinIO | 19000 (API), 19001 (Console) | S3 호환 오브젝트 스토리지 |
| Weaviate | 18080 | 벡터 데이터베이스 |

#### Docker Compose (배치)

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Celery Worker (backfill) | - | 논문 수집 워커 |
| Celery Worker (embed) | - | 임베딩 워커 |
| Celery Beat | - | 스케줄러 |
| Flower | 15555 | Celery 모니터링 UI |

#### 개발 서버

| 서비스 | 포트 | URL |
|--------|------|-----|
| Admin Backend (NestJS) | 13000 | http://localhost:13000 |
| Admin Frontend (Next.js) | 13001 | http://localhost:13001 |
| Service Backend (FastAPI) | 8000 | http://localhost:8000 |
| Service Frontend (Next.js) | 3000 | http://localhost:3000 |

### 유용한 URL

| 서비스 | URL |
|--------|-----|
| Admin 화면 | http://localhost:13001 |
| Admin API | http://localhost:13000 |
| User 화면 | http://localhost:3000 |
| User API 문서 (Swagger) | http://localhost:8000/docs |
| Flower (Celery 모니터링) | http://localhost:15555 |
| MinIO Console | http://localhost:19001 |

### 로그 확인

로그 파일은 `.dev-logs/` 폴더에 저장됩니다:

```bash
# 특정 서비스 로그 직접 확인
tail -f .dev-logs/admin-backend.log
tail -f .dev-logs/admin-frontend.log
tail -f .dev-logs/service-backend.log
tail -f .dev-logs/service-frontend.log

# 또는 메뉴로 선택
./scripts/dev.sh logs
```

### 트러블슈팅

#### 포트가 이미 사용 중일 때

```bash
# 특정 포트 사용 프로세스 확인
lsof -i :3000

# 프로세스 종료
kill -9 <PID>
```

#### 서비스가 시작되지 않을 때

```bash
# 로그 확인
./scripts/dev.sh logs

# 또는 직접 실행하여 에러 확인
cd admin/backend && npm run start:dev
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

#### Docker 서비스 문제

```bash
# 컨테이너 상태 확인
docker-compose ps

# 특정 서비스 로그 확인
docker-compose logs -f postgres
docker-compose logs -f celery-worker-backfill

# 컨테이너 재시작
docker-compose restart postgres
```

### 참고

- 첫 실행 시 Docker 이미지 빌드로 시간이 걸릴 수 있습니다
- `npm install` 또는 `uv sync`가 필요할 수 있습니다
- `.env` 파일 설정이 필요합니다 (`.env.example` 참고)
