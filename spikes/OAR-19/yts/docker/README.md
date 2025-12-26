# OAR-19 개발 환경

> PostgreSQL + MinIO (S3) 로컬 개발 환경

---

## 빠른 시작

```bash
cd spikes/OAR-19/yts/docker

# 시작
docker compose up -d

# 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f

# 종료
docker compose down

# 완전 삭제 (데이터 포함)
docker compose down -v
```

---

## 서비스 정보

### 포트 규칙

> `119XX` = 1 (prefix) + 19 (OAR-19) + XX (서비스)

| 서비스 | 포트 | 설명 |
|--------|------|------|
| PostgreSQL | `11932` | 119 + 32 (from 5432) |
| MinIO API | `11900` | 119 + 00 |
| MinIO Console | `11901` | 119 + 01 |

---

### PostgreSQL

| 항목 | 값 |
|------|-----|
| Host | `localhost` |
| Port | `11932` |
| Database | `oaria` |
| User | `oaria` |
| Password | `oaria_dev` |

**접속:**
```bash
# psql
psql -h localhost -p 11932 -U oaria -d oaria

# 또는 Docker 내부
docker exec -it oaria-postgres psql -U oaria -d oaria
```

**Python 연결:**
```python
import asyncpg

conn = await asyncpg.connect(
    host="localhost",
    port=11932,
    database="oaria",
    user="oaria",
    password="oaria_dev"
)
```

---

### MinIO (S3 호환)

| 항목 | 값 |
|------|-----|
| API Endpoint | `http://localhost:11900` |
| Console | `http://localhost:11901` |
| Access Key | `minioadmin` |
| Secret Key | `minioadmin` |
| Bucket | `oaria-papers` |

**Web Console:**
http://localhost:11901 (minioadmin / minioadmin)

**Python 연결 (boto3):**
```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:11900",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)

# 파일 업로드
s3.put_object(
    Bucket="oaria-papers",
    Key="canonical/pmc:PMC12345678/v1.txt",
    Body="논문 전문 텍스트..."
)
```

---

## 테이블 구조

### papers
```sql
-- 논문 메타데이터
SELECT paper_id, title, year, status FROM papers LIMIT 5;
```

### paper_authors
```sql
-- 저자 정보 (순서, ORCID, 소속)
SELECT author_name, author_order, orcid, affiliation
FROM paper_authors
WHERE paper_id = (SELECT id FROM papers WHERE paper_id = 'pmc:PMC12345678');
```

### paper_sections
```sql
-- 섹션 정보 (offset 포함)
SELECT section_name, offset_start, offset_end, char_count
FROM paper_sections
WHERE paper_id = (SELECT id FROM papers WHERE paper_id = 'pmc:PMC12345678');
```

### v_papers_summary (뷰)
```sql
-- 논문 요약 뷰
SELECT * FROM v_papers_summary ORDER BY created_at DESC LIMIT 10;
```

---

## 트러블슈팅

### 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i :5432
lsof -i :9000

# 다른 포트 사용 (docker-compose.yml 수정)
ports:
  - "5433:5432"  # PostgreSQL
```

### 데이터 초기화
```bash
docker compose down -v
docker compose up -d
```
