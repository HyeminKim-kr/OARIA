# OAR-31: Vector Store 설정 (Weaviate)

> 벡터 임베딩 저장 및 검색을 위한 Weaviate 설정

## 인수 조건

- [x] 10만+ 벡터 저장 가능 (HNSW 인덱스)
- [x] ANN 검색 지원 (Cosine 유사도)
- [x] 메타데이터 필터링 지원 (연도, 섹션, 저자 등)

## 구조

```
src/
├── schema.py      # PaperChunk 컬렉션 스키마 정의
├── embeddings.py  # OpenAI 임베딩 클라이언트
├── client.py      # Weaviate 클라이언트 (삽입/검색)
└── demo.py        # 데모 스크립트
```

## 실행 방법

```bash
# 1. Weaviate 시작
docker compose up -d

# 2. 의존성 설치
uv sync

# 3. 스키마 생성
uv run python src/schema.py create

# 4. 데모 실행 (OAR-29 Chunker 연동)
OPENAI_API_KEY=sk-xxx uv run python src/demo.py
```

## 검색 예시

```python
from src.client import WeaviateClient
from weaviate.classes.query import Filter

with WeaviateClient() as client:
    # 벡터 검색
    results = client.search_by_vector("cancer immunotherapy", limit=5)

    # 하이브리드 검색 (벡터 + 키워드)
    results = client.search_hybrid("lung cancer treatment", alpha=0.5)

    # 필터 + 검색
    results = client.search_by_vector(
        "immunotherapy response",
        filters=Filter.by_property("year").greater_or_equal(2020),
    )
```
