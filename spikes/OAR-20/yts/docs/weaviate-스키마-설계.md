# Weaviate 스키마 설계

> **OAR-20**: 논문 스키마 설계 및 구현
>
> 결정: Weaviate (Vector DB) 사용
>
> 작성일: 2025-12-19

---

## 설계 방향

### 핵심 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| **Vector DB** | Weaviate | 텍스트+벡터 통합 저장, GraphQL 지원 |
| **임베딩** | 외부 처리 (BYOV) | 모델 선택 유연성, 비용 제어 |
| **저장 단위** | 청크 | 검색 정밀도, RAG 최적화 |
| **임베딩 버전 전략** | 컬렉션 분리 (A) | 운영 단순, 마이그레이션 명확 |

### 임베딩 버전 관리 전략

> **결정: A) 모델 변경 시 컬렉션 새로 생성**

```
모델 변경 시:
PaperChunk (v1: text-embedding-3-small)
    ↓ 모델 변경
PaperChunk_v2 (v2: text-embedding-3-large)
```

**선택 이유:**
- 운영이 단순 (버전 혼재 없음)
- 마이그레이션이 명확 (구 컬렉션 삭제 가능)
- 검색 품질 보장 (같은 모델로 임베딩된 데이터만 비교)

**대안 B) 같은 컬렉션 공존** (채택 안 함):
- UUID에 embeddingVersion 포함 필요
- 검색 시 버전 필터 필수
- 복잡도 증가

### 임베딩 처리 방식

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  텍스트     │ ──▶ │ 임베딩 서비스│ ──▶ │  Weaviate   │
│  (청크)     │     │ (별도 처리)  │     │ (벡터 저장) │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    OpenAI / Cohere /
                    로컬 모델 등 선택 가능
```

**Weaviate 설정:**
```python
vectorizer_config=wvc.config.Configure.Vectorizer.none()  # BYOV
```

---

## Collection 스키마

### PaperChunk Collection

> **주의**: 논문 1편이 아닌 **청크 단위**로 저장됨

```python
import weaviate
import weaviate.classes as wvc

paper_chunk_schema = {
    "name": "PaperChunk",
    "description": "암 논문 청크 데이터 (RAG 검색용)",

    # 임베딩 비활성화 (외부에서 직접 벡터 제공)
    "vectorizer_config": wvc.config.Configure.Vectorizer.none(),

    # 벡터 인덱스 설정 (HNSW)
    "vector_index_config": wvc.config.Configure.VectorIndex.hnsw(
        distance_metric=wvc.config.VectorDistances.COSINE,
        ef_construction=128,  # 인덱스 빌드 품질 (높을수록 정확, 느림)
        max_connections=64    # HNSW 그래프 연결 수
        # ef는 쿼리 시점 파라미터이므로 여기서 설정 안 함
    ),

    "properties": [
        # ─────────────────────────────────────
        # 내부 식별자 (운영/마이그레이션용)
        # ─────────────────────────────────────
        {
            "name": "paperId",
            "dataType": wvc.config.DataType.TEXT,
            "description": "논문 통일 ID (예: pmid:12345678 또는 doi:10.1000/xyz)",
            "index_filterable": True,
            "index_searchable": False
        },
        {
            "name": "chunkId",
            "dataType": wvc.config.DataType.TEXT,
            "description": "청크 고유 ID (예: pmid:12345678|methods|0)",
            "index_filterable": True,
            "index_searchable": False
        },
        {
            "name": "embeddingVersion",
            "dataType": wvc.config.DataType.TEXT,
            "description": "임베딩 모델 버전 (예: openai:text-embedding-3-small:v1)",
            "index_filterable": True,
            "index_searchable": False
        },

        # ─────────────────────────────────────
        # 외부 논문 식별자
        # ─────────────────────────────────────
        {
            "name": "pmcid",
            "dataType": wvc.config.DataType.TEXT,
            "description": "PMC 고유 ID (예: PMC12345678)",
            "index_filterable": True,
            "index_searchable": False
        },
        {
            "name": "pmid",
            "dataType": wvc.config.DataType.TEXT,
            "description": "PubMed ID",
            "index_filterable": True,
            "index_searchable": False
        },
        {
            "name": "doi",
            "dataType": wvc.config.DataType.TEXT,
            "description": "DOI",
            "index_filterable": True,
            "index_searchable": False
        },

        # ─────────────────────────────────────
        # 논문 메타데이터
        # ─────────────────────────────────────
        {
            "name": "title",
            "dataType": wvc.config.DataType.TEXT,
            "description": "논문 제목",
            "index_filterable": False,
            "index_searchable": True  # BM25 키워드 검색
        },
        {
            "name": "authors",
            "dataType": wvc.config.DataType.TEXT_ARRAY,
            "description": "저자 목록",
            "index_filterable": True,   # 저자 필터링 가능
            "index_searchable": False
        },
        {
            "name": "journal",
            "dataType": wvc.config.DataType.TEXT,
            "description": "저널명",
            "index_filterable": True,
            "index_searchable": False
        },
        {
            "name": "year",
            "dataType": wvc.config.DataType.INT,
            "description": "출판 연도",
            "index_filterable": True,   # WHERE year >= 2020
            "index_searchable": False
        },
        {
            "name": "keywords",
            "dataType": wvc.config.DataType.TEXT_ARRAY,
            "description": "키워드 목록",
            "index_filterable": True,
            "index_searchable": False
        },

        # ─────────────────────────────────────
        # 청크 정보
        # ─────────────────────────────────────
        {
            "name": "section",
            "dataType": wvc.config.DataType.TEXT,
            "description": "섹션 유형 (abstract, introduction, methods, results, discussion, conclusion)",
            "index_filterable": True,   # WHERE section = "methods"
            "index_searchable": False
        },
        {
            "name": "chunkIndex",
            "dataType": wvc.config.DataType.INT,
            "description": "섹션 내 청크 순서 (0부터 시작)",
            "index_filterable": True,   # 디버깅/재현성 (청크 범위 조회)
            "index_searchable": False
        },
        {
            "name": "content",
            "dataType": wvc.config.DataType.TEXT,
            "description": "청크 텍스트 내용 (검색 대상)",
            "index_filterable": False,
            "index_searchable": True   # BM25 하이브리드 검색
        },

        # ─────────────────────────────────────
        # 원문 위치 (재현성/감사용)
        # ─────────────────────────────────────
        {
            "name": "offsetStart",
            "dataType": wvc.config.DataType.INT,
            "description": "표준 원문(canonical text)에서 시작 위치 (문자 인덱스)",
            "index_filterable": False,
            "index_searchable": False
        },
        {
            "name": "offsetEnd",
            "dataType": wvc.config.DataType.INT,
            "description": "표준 원문(canonical text)에서 끝 위치 (문자 인덱스)",
            "index_filterable": False,
            "index_searchable": False
        },
        {
            "name": "textVersion",
            "dataType": wvc.config.DataType.TEXT,
            "description": "표준 원문 버전 (예: canonical_v1)",
            "index_filterable": True,
            "index_searchable": False
        },

        # ─────────────────────────────────────
        # 메타 정보
        # ─────────────────────────────────────
        {
            "name": "sourceUrl",
            "dataType": wvc.config.DataType.TEXT,
            "description": "원본 논문 URL",
            "index_filterable": False,
            "index_searchable": False
        },
        {
            "name": "createdAt",
            "dataType": wvc.config.DataType.DATE,
            "description": "수집 일시",
            "index_filterable": True,
            "index_searchable": False
        }
    ]
}
```

---

## ID 생성 규칙

### paperId (논문 통일 ID)

```python
def generate_paper_id(pmid: str | None, pmcid: str | None, doi: str | None) -> str:
    """우선순위: pmid > pmcid > doi"""
    if pmid:
        return f"pmid:{pmid}"
    if pmcid:
        return f"pmc:{pmcid}"
    if doi:
        return f"doi:{doi}"
    raise ValueError("최소 하나의 ID 필요")

# 예: "pmid:12345678"
```

### chunkId (청크 고유 ID)

```python
def generate_chunk_id(paper_id: str, section: str, chunk_index: int) -> str:
    """결정적 ID 생성"""
    return f"{paper_id}|{section}|{chunk_index}"

# 예: "pmid:12345678|methods|0"
```

### UUID 생성 (Weaviate object ID)

```python
import uuid

def generate_uuid_from_chunk_id(chunk_id: str) -> str:
    """chunk_id로 결정적 UUID 생성 (중복 방지, 재적재 용이)"""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

# 같은 chunk_id → 항상 같은 UUID
```

### embeddingVersion

```python
EMBEDDING_VERSION = "openai:text-embedding-3-small:v1"

# 모델 변경 시 버전 업데이트
# 예: "openai:text-embedding-3-large:v1"
# 예: "cohere:embed-english-v3.0:v1"
```

---

## 인덱스 설정 가이드

### 인덱스 타입별 용도

| 인덱스 | 용도 | 비용 | 권장 |
|--------|------|------|------|
| `index_filterable` | WHERE 조건 | 중간 | 필터 필요한 필드만 |
| `index_searchable` | BM25 키워드 | 높음 | 최소화 권장 |
| 벡터 인덱스 | 유사도 검색 | 높음 | 기본 활성화 |

### 현재 설정

| 필드 | filterable | searchable | 이유 |
|------|------------|------------|------|
| `paperId` | O | X | 논문별 조회 |
| `chunkId` | O | X | 청크 식별 |
| `embeddingVersion` | O | X | 버전별 필터 |
| `pmcid`, `pmid`, `doi` | O | X | 외부 ID 조회 |
| `title` | X | O | 키워드 검색 |
| `authors` | O | X | 저자 필터 |
| `journal` | O | X | 저널 필터 |
| `year` | O | X | 연도 필터 |
| `section` | O | X | 섹션 필터 |
| `chunkIndex` | O | X | 디버깅/재현성 |
| `content` | X | O | 하이브리드 검색 (MVP) |
| `offsetStart`, `offsetEnd` | X | X | 저장만 (재현용) |
| `textVersion` | O | X | 표준원문 버전 필터 |

> **주의**: 대규모(수천만 객체) 시 인덱스 비용 증가. 필요한 것만 활성화.

### content searchable 스케일업 전략

| 단계 | content searchable | 하이브리드 대상 | 비고 |
|------|-------------------|----------------|------|
| **MVP** | O | content + title | 품질 확인용 |
| **스케일업** | X | title, keywords만 | 벡터 검색 중심 |
| **대안** | X + 별도 필드 | `lexicalContent` (요약) | 정제 텍스트만 searchable |

```python
# 스케일업 시 content searchable 끄기
wvc.config.Property(
    name="content",
    data_type=wvc.config.DataType.TEXT,
    index_searchable=False  # 벡터 검색만 사용
)

# 대안: 짧은 요약 필드 추가
wvc.config.Property(
    name="lexicalContent",  # 키워드 추출/요약 텍스트
    data_type=wvc.config.DataType.TEXT,
    index_searchable=True
)
```

---

## 원문 위치 추적 (재현성/감사)

### 왜 offset이 필요한가?

```
문제: chunkIndex는 청킹 로직이 바뀌면 의미가 달라짐

청크 크기 500 → 800 변경
    → 같은 문장이 chunkIndex=7 에서 chunkIndex=5 로 이동

offset은 "원문 텍스트의 절대 좌표"
    → 청킹 로직이 바뀌어도 원문 위치는 동일
```

### 표준 원문 (Canonical Text)

```python
# 논문마다 "표준 원문"을 정의
canonical_text = normalize_text(
    sections=["abstract", "introduction", "methods", "results", "discussion"],
    rules={
        "whitespace": "single_space",
        "unicode": "NFC",
        "line_breaks": "removed"
    }
)

# 청크는 항상 canonical_text에서 슬라이싱
chunk_text = canonical_text[offset_start:offset_end]
```

### offset 계산 예시

```python
def create_chunks_with_offset(canonical_text: str, chunk_size: int = 1000):
    """표준 원문에서 청크 생성 + offset 기록"""
    chunks = []
    start = 0

    while start < len(canonical_text):
        end = min(start + chunk_size, len(canonical_text))

        chunks.append({
            "content": canonical_text[start:end],
            "offsetStart": start,
            "offsetEnd": end,
            "textVersion": "canonical_v1"
        })

        start = end

    return chunks
```

### 재현/감사 활용

```python
# 1. 답변 근거 저장 시
answer_evidence = {
    "paperId": "pmid:12345678",
    "offsetStart": 12340,
    "offsetEnd": 13210,
    "textVersion": "canonical_v1"
}

# 2. 나중에 정확히 재현
canonical_text = get_canonical_text(paper_id, text_version)
evidence_text = canonical_text[12340:13210]  # 정확히 같은 문장

# 3. UI에서 하이라이트
highlight_range(paper_view, start=12340, end=13210)
```

### textVersion 관리

| 버전 | 설명 | 변경 사유 |
|------|------|----------|
| `canonical_v1` | 초기 버전 | - |
| `canonical_v2` | 표/캡션 추가 | 구조 변경 |
| `canonical_v3` | 정규화 규칙 변경 | 품질 개선 |

> **원칙**: textVersion이 바뀌면 해당 논문의 청크는 재생성 필요

---

## 데이터 저장 구조

### 비정규화 (Denormalized)

```
논문 1개 = 여러 개의 PaperChunk 객체

┌─────────────────────────────────────────────────────┐
│ PaperChunk 객체 1                                   │
│ ─────────────────                                   │
│ paperId: "pmid:12345678"                            │
│ chunkId: "pmid:12345678|abstract|0"                 │
│ embeddingVersion: "openai:text-embedding-3-small:v1"│
│ pmcid: "PMC12345678"                                │
│ title: "Immunotherapy in Lung Cancer"  ← 중복 저장  │
│ year: 2024                             ← 중복 저장  │
│ section: "abstract"                                 │
│ chunkIndex: 0                                       │
│ content: "Background: Immune checkpoint..."         │
│ offsetStart: 0                         ← 원문 위치  │
│ offsetEnd: 1250                                     │
│ textVersion: "canonical_v1"                         │
│ vector: [0.12, -0.34, 0.56, ...]       ← 임베딩     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ PaperChunk 객체 2                                   │
│ ─────────────────                                   │
│ paperId: "pmid:12345678"               ← 같은 논문  │
│ chunkId: "pmid:12345678|methods|0"                  │
│ embeddingVersion: "openai:text-embedding-3-small:v1"│
│ pmcid: "PMC12345678"                                │
│ title: "Immunotherapy in Lung Cancer"               │
│ year: 2024                                          │
│ section: "methods"                                  │
│ chunkIndex: 0                                       │
│ content: "We conducted a randomized trial..."       │
│ offsetStart: 5200                      ← 원문 위치  │
│ offsetEnd: 6450                                     │
│ textVersion: "canonical_v1"                         │
│ vector: [0.78, 0.12, -0.45, ...]                    │
└─────────────────────────────────────────────────────┘
```

### 저장 예상량

| 논문 수 | 평균 청크/논문 | 총 객체 수 |
|---------|---------------|-----------|
| 1,000 | 5~10 | 5,000~10,000 |
| 10,000 | 5~10 | 50,000~100,000 |
| 100,000 | 5~10 | 500,000~1,000,000 |

---

## Python 클라이언트 예시 (v4)

### 연결 및 컬렉션 생성

```python
import weaviate
import weaviate.classes as wvc

# 연결
client = weaviate.connect_to_local()  # localhost:8080

# 컬렉션 생성
client.collections.create(
    name="PaperChunk",
    description="암 논문 청크 데이터 (RAG 검색용)",
    vectorizer_config=wvc.config.Configure.Vectorizer.none(),
    vector_index_config=wvc.config.Configure.VectorIndex.hnsw(
        distance_metric=wvc.config.VectorDistances.COSINE,
        ef_construction=128,
        max_connections=64
    ),
    properties=[
        # 내부 식별자
        wvc.config.Property(name="paperId", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        wvc.config.Property(name="chunkId", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        wvc.config.Property(name="embeddingVersion", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        # 외부 식별자
        wvc.config.Property(name="pmcid", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        wvc.config.Property(name="pmid", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        wvc.config.Property(name="doi", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        # 메타데이터
        wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT, index_searchable=True),
        wvc.config.Property(name="authors", data_type=wvc.config.DataType.TEXT_ARRAY, index_filterable=True),
        wvc.config.Property(name="journal", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        wvc.config.Property(name="year", data_type=wvc.config.DataType.INT, index_filterable=True),
        wvc.config.Property(name="keywords", data_type=wvc.config.DataType.TEXT_ARRAY, index_filterable=True),
        # 청크 정보
        wvc.config.Property(name="section", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        wvc.config.Property(name="chunkIndex", data_type=wvc.config.DataType.INT, index_filterable=True),
        wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT, index_searchable=True),
        # 원문 위치 (재현성/감사용)
        wvc.config.Property(name="offsetStart", data_type=wvc.config.DataType.INT),
        wvc.config.Property(name="offsetEnd", data_type=wvc.config.DataType.INT),
        wvc.config.Property(name="textVersion", data_type=wvc.config.DataType.TEXT, index_filterable=True),
        # 메타 정보
        wvc.config.Property(name="sourceUrl", data_type=wvc.config.DataType.TEXT),
        wvc.config.Property(name="createdAt", data_type=wvc.config.DataType.DATE, index_filterable=True),
    ]
)
```

### 데이터 삽입 (벡터 직접 제공)

```python
import uuid

# 컬렉션 가져오기
paper_chunks = client.collections.get("PaperChunk")

# ID 생성
paper_id = "pmid:12345678"
chunk_id = f"{paper_id}|abstract|0"
object_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id)

# 임베딩 생성 (외부 서비스)
embedding = get_embedding("Background: Immune checkpoint...")  # OpenAI 등

# 삽입
paper_chunks.data.insert(
    uuid=object_uuid,
    properties={
        "paperId": paper_id,
        "chunkId": chunk_id,
        "embeddingVersion": "openai:text-embedding-3-small:v1",
        "pmcid": "PMC12345678",
        "pmid": "12345678",
        "doi": "10.1000/example.2024.001",
        "title": "Immunotherapy in Lung Cancer",
        "authors": ["Kim J", "Lee S"],
        "journal": "Nature Medicine",
        "year": 2024,
        "keywords": ["lung cancer", "immunotherapy", "pembrolizumab"],
        "section": "abstract",
        "chunkIndex": 0,
        "content": "Background: Immune checkpoint...",
        "offsetStart": 0,
        "offsetEnd": 1250,
        "textVersion": "canonical_v1",
        "sourceUrl": "https://europepmc.org/article/PMC/12345678"
    },
    vector=embedding
)
```

### 벡터 유사도 검색

```python
# 질문 임베딩
query_vector = get_embedding("폐암 3기 면역치료 효과")

# 검색
response = paper_chunks.query.near_vector(
    near_vector=query_vector,
    limit=5,
    return_metadata=wvc.query.MetadataQuery(distance=True)
)

for obj in response.objects:
    print(f"{obj.properties['title']} - {obj.properties['section']}")
    print(f"  Distance: {obj.metadata.distance}")
```

### 필터 + 벡터 검색

```python
from weaviate.classes.query import Filter

response = paper_chunks.query.near_vector(
    near_vector=query_vector,
    filters=(
        Filter.by_property("year").greater_or_equal(2020) &
        Filter.by_property("section").equal("results")
    ),
    limit=5
)
```

### 저자 필터 검색

```python
# "Kim J" 저자의 논문에서 검색
response = paper_chunks.query.near_vector(
    near_vector=query_vector,
    filters=Filter.by_property("authors").contains_any(["Kim J"]),
    limit=5
)
```

### 하이브리드 검색 (벡터 + 키워드)

```python
response = paper_chunks.query.hybrid(
    query="lung cancer immunotherapy",
    vector=query_vector,
    alpha=0.5,  # 0=키워드, 1=벡터, 0.5=균형
    limit=5
)
```

### 특정 논문의 모든 청크 조회

```python
response = paper_chunks.query.fetch_objects(
    filters=Filter.by_property("paperId").equal("pmid:12345678"),
    sort=wvc.query.Sort.by_property("chunkIndex", ascending=True)
)
```

### 청크 범위 조회 (디버깅/재현용)

```python
# results 섹션의 0~2번 청크만 조회
response = paper_chunks.query.fetch_objects(
    filters=(
        Filter.by_property("paperId").equal("pmid:12345678") &
        Filter.by_property("section").equal("results") &
        Filter.by_property("chunkIndex").less_or_equal(2)
    )
)

# 특정 chunkId로 정확히 재현
response = paper_chunks.query.fetch_objects(
    filters=Filter.by_property("chunkId").equal("pmid:12345678|results|1")
)
```

### 임베딩 버전별 조회/삭제 (마이그레이션용)

```python
# 특정 버전 조회
old_version = paper_chunks.query.fetch_objects(
    filters=Filter.by_property("embeddingVersion").equal("openai:text-embedding-ada-002:v1"),
    limit=1000
)

# 특정 버전 삭제
paper_chunks.data.delete_many(
    where=Filter.by_property("embeddingVersion").equal("openai:text-embedding-ada-002:v1")
)
```

---

## 배포 옵션

### 1. Docker (개발/테스트)

```yaml
# docker-compose.yml
version: '3.8'
services:
  weaviate:
    image: semitechnologies/weaviate:1.28.0
    ports:
      - "8080:8080"
      - "50051:50051"  # gRPC
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
      CLUSTER_HOSTNAME: 'node1'
    volumes:
      - weaviate_data:/var/lib/weaviate

volumes:
  weaviate_data:
```

```bash
docker compose up -d
```

### 2. Weaviate Cloud (프로덕션)

- 관리형 서비스
- 자동 스케일링
- 백업/복구

---

## HNSW 튜닝 가이드

### 인덱스 빌드 파라미터 (스키마 설정)

| 파라미터 | 기본값 | 설명 | 권장 |
|----------|--------|------|------|
| `ef_construction` | 128 | 인덱스 빌드 품질 | 64~256 (높으면 정확, 느림) |
| `max_connections` | 64 | 노드당 연결 수 | 32~128 |

### 쿼리 파라미터 (검색 시점)

| 파라미터 | 기본값 | 설명 | 설정 위치 |
|----------|--------|------|----------|
| `ef` | -1 (동적) | 검색 정확도 | 쿼리 시 설정 |

```python
# 쿼리 시 ef 설정
response = paper_chunks.query.near_vector(
    near_vector=query_vector,
    limit=5,
    # ef는 Weaviate가 자동 조정 (limit의 배수)
)
```

> **권장**: 기본값으로 시작 → 실제 데이터로 recall/latency 측정 → 필요시 튜닝

---

## 다음 단계

- [ ] Docker로 로컬 Weaviate 실행
- [ ] 스키마 생성 스크립트 작성
- [ ] 샘플 데이터 100건 삽입 테스트
- [ ] 검색 쿼리 테스트 (저자, 연도, 섹션 필터)
- [ ] 하이브리드 검색 테스트
- [ ] 임베딩 버전 마이그레이션 테스트

---

## 참고

- [Weaviate Collections (v4)](https://weaviate.io/developers/weaviate/manage-data/collections)
- [Weaviate BYOV (Bring Your Own Vectors)](https://weaviate.io/developers/weaviate/starter-guides/custom-vectors)
- [Weaviate HNSW Config](https://weaviate.io/developers/weaviate/config-refs/schema/vector-index#hnsw-index-parameters)
- [Weaviate Python Client v4](https://weaviate.io/developers/weaviate/client-libraries/python)
