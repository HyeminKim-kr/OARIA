# OAR-20: 논문 스키마 설계

> **담당**: yts
>
> **목적**: 암 논문 RAG 시스템을 위한 데이터베이스 스키마 설계

---

## 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| **Vector DB** | Weaviate | 텍스트+벡터 통합, GraphQL 지원 |
| **서비스 DB** | PostgreSQL | 관계형 데이터, 트랜잭션 |
| **원문 저장** | S3 | 대용량 텍스트, 비용 효율 |
| **임베딩** | 외부 처리 (BYOV) | 모델 선택 유연성 |
| **저장 단위** | 청크 (비정규화) | 검색 정밀도 |

---

## 폴더 구조

```
OAR-20/yts/
├── README.md                         # 이 문서
├── docs/
│   ├── weaviate-스키마-설계.md        # Weaviate 스키마 상세
│   └── postgresql-스키마-설계-v2.3.md  # PostgreSQL + S3 스키마 (v2.3)
└── tmp/                              # 이전 수집기 코드 (임시)
```

---

## 스키마 요약

### PaperChunk Collection

> 논문 1편이 아닌 **청크 단위**로 저장

```python
{
    "name": "PaperChunk",
    "vectorizer_config": "none",  # 임베딩 외부 처리

    "properties": [
        # 내부 식별자
        {"name": "paperId", ...},        # pmid:12345678
        {"name": "chunkId", ...},        # pmid:12345678|methods|0
        {"name": "embeddingVersion", ...}, # openai:text-embedding-3-small:v1

        # 외부 식별자
        {"name": "pmcid", ...},
        {"name": "pmid", ...},
        {"name": "doi", ...},

        # 메타데이터
        {"name": "title", ...},
        {"name": "authors", ...},        # filterable=True
        {"name": "journal", ...},
        {"name": "year", ...},           # filterable=True

        # 청크 정보
        {"name": "section", ...},        # filterable=True
        {"name": "chunkIndex", ...},
        {"name": "content", ...}         # searchable=True (BM25)
    ]
}
```

---

## 진행 상황

- [x] Vector DB 선정 (Weaviate)
- [x] Weaviate 스키마 설계 (PaperChunk)
- [x] PostgreSQL + S3 스키마 설계 (서비스 DB)
- [ ] Backend API 설계
- [ ] Docker 환경 구성
- [ ] 샘플 데이터 테스트

---

## 관련 문서

- [Weaviate 스키마 설계](./docs/weaviate-스키마-설계.md) - 벡터 검색용
- [PostgreSQL + S3 스키마 설계 (v2.3)](./docs/postgresql-스키마-설계-v2.3.md) - 서비스 DB
- [데이터 수집 전략](../../OAR-9/tsy/데이터-수집-전략.md)
