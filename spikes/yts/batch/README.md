# Batch Processing System

암 논문 수집 및 임베딩 배치 시스템 (Celery 기반)

## 개요

- **논문 수집** (`backfill`): Europe PMC에서 논문 검색 및 수집
- **임베딩** (`embed`): 수집된 논문을 청킹하고 벡터 임베딩하여 Weaviate에 저장

## 의존성

- OAR-29: TextChunker (섹션 기반 청킹)
- OAR-31: EmbeddingClient, WeaviateClient (벡터 임베딩 및 저장)

## 인프라 요구사항

```bash
# Docker Compose로 인프라 시작
cd spikes/yts/infra
docker compose up -d

# 컨테이너 확인
docker compose ps
```

| 서비스 | 포트 | 설명 |
|--------|------|------|
| PostgreSQL | 15432 | 논문 메타데이터 DB |
| MinIO | 19000 | S3 호환 오브젝트 스토리지 |
| Redis | 16379 | Celery 브로커 |
| Weaviate | 8080 | 벡터 DB (OAR-31에서 실행) |

## 환경변수

```bash
# 필수
export OPENAI_API_KEY=sk-xxx

# 선택 (기본값 있음)
export DB_HOST=localhost
export DB_PORT=15432
export S3_ENDPOINT=http://localhost:19000
export REDIS_HOST=localhost
export REDIS_PORT=16379
export WEAVIATE_HOST=localhost
export WEAVIATE_PORT=8080
```

## 워커 실행

### 논문 수집 워커 (backfill 큐)

```bash
cd spikes/yts/batch
celery -A src.celery_app worker --loglevel=info -Q backfill
```

### 임베딩 워커 (embed 큐)

```bash
cd spikes/yts/batch
celery -A src.celery_app worker --loglevel=info -Q embed
```

### 모든 큐 처리 (개발용)

```bash
cd spikes/yts/batch
celery -A src.celery_app worker --loglevel=info -Q backfill,embed,incremental,repair
```

## 태스크 실행

### Python 코드에서 호출

```python
from src.tasks.backfill import run_backfill
from src.tasks.embed import run_embed, run_embed_paper

# 논문 수집 (비동기)
result = run_backfill.delay(query_id="<search_query_id>")
print(result.get())  # 결과 대기

# 수집된 논문 일괄 임베딩
result = run_embed.delay(query_id="<search_query_id>")
print(result.get())

# 전체 논문 임베딩 (query_id 없이)
result = run_embed.delay()
print(result.get())

# 단일 논문 임베딩
result = run_embed_paper.delay(paper_id="pmc:PMC12345678")
print(result.get())

# 실패한 논문 재임베딩
from src.tasks.embed import run_reembed
result = run_reembed.delay()
print(result.get())
```

### CLI에서 호출

```bash
cd spikes/yts/batch

# 수집 태스크 실행
python -c "from src.tasks.backfill import run_backfill; print(run_backfill.delay('<query_id>'))"

# 임베딩 태스크 실행
python -c "from src.tasks.embed import run_embed; print(run_embed.delay())"
```

## 임베딩 파이프라인 흐름

```
1. PostgreSQL에서 수집된 논문 조회
   └── papers 테이블 (embedding_status = NULL or 'pending')

2. S3/MinIO에서 fulltext.txt 읽기
   └── {canonical_prefix}/fulltext.txt

3. OAR-29 TextChunker로 청킹
   └── 섹션 기반 + Recursive splitting
   └── offset 추적 (근거 재현용)

4. OpenAI 임베딩 생성
   └── text-embedding-3-small (1536 차원)
   └── 배치 처리 (10개씩)

5. Weaviate에 저장
   └── PaperChunk 컬렉션
   └── 하이브리드 검색 지원 (벡터 + BM25)

6. PostgreSQL 상태 업데이트
   └── embedding_status = 'completed'
   └── embedding_chunk_count = N
```

## DB 마이그레이션

### 신규 설치 (컨테이너 최초 생성)

`infra/init/` 폴더가 Docker에 마운트되어 있어 자동 실행됩니다:

```bash
cd spikes/yts/infra
docker compose down -v  # 볼륨 삭제 (주의: 데이터 삭제됨)
docker compose up -d    # 01-schema.sql, 02-embedding-columns.sql 자동 실행
```

### 기존 환경에 마이그레이션 적용

이미 실행 중인 컨테이너에 임베딩 컬럼 추가:

```bash
# 방법 1: docker exec 사용
docker exec -i yts-postgres psql -U oaria -d oaria < infra/init/02-embedding-columns.sql

# 방법 2: docker compose exec 사용
cd spikes/yts/infra
docker compose exec -T postgres psql -U oaria -d oaria < init/02-embedding-columns.sql
```

## 모니터링

### Celery 상태 확인

```bash
celery -A src.celery_app inspect active
celery -A src.celery_app inspect reserved
celery -A src.celery_app inspect stats
```

### Flower (웹 UI)

```bash
pip install flower
celery -A src.celery_app flower --port=5555
# http://localhost:5555
```

## 태스크 목록

| 태스크 | 큐 | 설명 |
|--------|------|------|
| `run_backfill` | backfill | 논문 수집 (검색 → 다운로드 → 파싱 → 저장) |
| `run_backfill_resume` | backfill | 중단된 수집 재개 |
| `run_embed` | embed | 수집된 논문 일괄 임베딩 |
| `run_embed_paper` | embed | 단일 논문 임베딩 |
| `run_reembed` | embed | 실패한 논문 재임베딩 |

## 트러블슈팅

### Weaviate 연결 실패

```bash
# OAR-31에서 Weaviate 실행
cd spikes/OAR-31/yts
docker compose up -d
```

### OpenAI API 키 없음

```
⚠️ OPENAI_API_KEY가 없습니다. Mock 모드로 전환합니다.
```

→ Mock 모드는 테스트용으로, 실제 임베딩은 생성되지 않습니다.

### 논문을 찾을 수 없음

```
ValueError: Paper not found: pmc:PMC12345678
```

→ 먼저 `run_backfill` 태스크로 논문을 수집해야 합니다.

### Fulltext 없음

```
ValueError: Fulltext not found: canonical/pmc_PMC12345678
```

→ S3에 fulltext.txt가 저장되지 않았습니다. 논문 수집을 다시 실행하세요.
