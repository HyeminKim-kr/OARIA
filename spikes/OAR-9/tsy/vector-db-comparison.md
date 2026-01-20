# Vector DB 비교 분석 (객관적 조사)

> OAR-20 사전조사: 벡터 데이터베이스 선택
>
> 작성일: 2025-12-18
> 목적: 팀 의사결정을 위한 객관적 자료 제공 (결론 미확정)

---

## 벤치마크 신뢰성 주의사항

### 벤더 벤치마크의 한계

> "When selecting a vector database for your AI application, conventional benchmarks are like test-driving a sports car on an empty track, only to find it stalls in rush hour traffic."
> — [Milvus Blog: Benchmarks Lie](https://milvus.io/blog/benchmarks-lie-vector-dbs-deserve-a-real-test.md)

**주요 문제점:**

| 문제 | 설명 |
|------|------|
| **정적 환경 테스트** | 대부분 인덱스 빌드 완료 후 테스트. 실제 프로덕션은 데이터가 계속 유입됨 |
| **구식 데이터셋** | SIFT(128D) 등 2006-2012년 데이터셋 사용. 현대 임베딩은 768-3,072D |
| **벤더 이해관계** | 각 벤더가 자사에 유리한 조건으로 벤치마크 수행 |
| **DeWitt Clause** | Pinecone, ElasticSearch 등 일부 벤더는 벤치마크 공개 자체를 금지 |

> 출처: [benchANT - DeWitt Clause](https://benchant.com/blog/vectordb-de-witt), [Milvus VDBBench](https://milvus.io/blog/vdbbench-1-0-benchmarking-with-your-real-world-production-workloads.md)

### 독립 벤치마크 도구

| 도구 | 특징 | 출처 |
|------|------|------|
| **ANN-Benchmarks** | 알고리즘 레벨 비교, 다수 벤더 참여 | [ann-benchmarks.com](https://ann-benchmarks.com/) |
| **VectorDBBench** | Zilliz(Milvus) 개발, 실제 환경 시뮬레이션 | [GitHub](https://github.com/zilliztech/VectorDBBench) |
| **vector-db-benchmark** | Qdrant 개발, 다수 벤더 기여 가능 | [GitHub](https://github.com/qdrant/vector-db-benchmark) |

**주의**: 독립 도구도 특정 벤더가 만든 것이므로 완전한 중립은 아님.

---

## 각 Vector DB 분석

### 1. pgvector (PostgreSQL 확장)

**기본 정보**
- 버전: v0.8.1
- 개발: PostgreSQL 커뮤니티
- 라이선스: PostgreSQL License (오픈소스)

**장점**
- PostgreSQL 인프라 통합 (별도 DB 불필요)
- SQL로 벡터 + 메타데이터 동시 쿼리
- 트랜잭션 일관성
- 운영 단순화

**단점 및 실제 프로덕션 이슈**

> 출처: [The Case Against pgvector](https://alex-jacobs.com/posts/the-case-against-pgvector/), [Supabase 성능 튜닝](https://medium.com/@dikhyantkrishnadalai/optimizing-vector-search-at-scale-lessons-from-pgvector-supabase-performance-tuning-ce4ada4ba2ed)

| 이슈 | 상세 |
|------|------|
| **스케일 성능 저하** | 10M 벡터 이후 50ms → 800ms 지연 증가 사례 |
| **메모리 요구량** | 50M 벡터(768D) 기준 ~852GB 메모리 필요 |
| **인덱스 리빌드** | 메모리 집약적, 시간 소요, 서비스 중단 가능 |
| **쿼리 플래너** | 필터 + 벡터 검색 조합 시 최적화 미흡 |
| **수평 확장 어려움** | 샤딩 구현에 6개월+ 엔지니어링 필요 사례 |
| **AWS RDS 제한** | pgvectorscale 미지원 |

**pgvectorscale 추가 시**
- Timescale이 개발한 확장
- StreamingDiskANN 인덱스로 메모리 효율 개선
- 50M 벡터에서 sub-100ms 달성 가능
- 단, AWS RDS 등 관리형 서비스에서 미지원

---

### 2. Qdrant

**기본 정보**
- 버전: v1.16.2 (2025.12)
- 개발 언어: Rust
- 라이선스: Apache 2.0

**장점**

> 출처: [Qdrant Benchmarks](https://qdrant.tech/benchmarks/)

- 복잡한 메타데이터 필터링에 강점
- Rust 기반 안정성/성능
- Docker 배포 용이
- REST/gRPC API

**단점 및 실제 프로덕션 이슈**

> 출처: [Qdrant GitHub Issues](https://github.com/qdrant/qdrant/issues), [Qdrant Troubleshooting](https://qdrant.tech/documentation/guides/common-errors/)

| 이슈 | 상세 |
|------|------|
| **느린 인덱싱** | 10,000 포인트에 3시간+ 인덱싱 지연 사례 (2024.12) |
| **파일시스템 제한** | POSIX 호환 필수, HFS+/FUSE 문제 |
| **정적 샤딩** | 데이터 증가 시 수동 리샤딩 필요 |
| **대용량 삽입 문제** | 대량 포인트 삽입 시 효율성 저하 보고 |
| **기본 설정 부족** | 프로덕션에서 기본값으로 메모리 에러 발생 |

---

### 3. Milvus

**기본 정보**
- 버전: 2.x
- 개발 언어: Go + C++
- 라이선스: Apache 2.0
- GitHub Stars: ~25k (가장 많음)

**장점**

> 출처: [Milvus Documentation](https://milvus.io/docs/)

- **수십억 벡터** 스케일링 설계
- GPU 가속 지원
- 분산 아키텍처
- 분자 구조 유사도 검색 등 **제약/바이오 특화 기능**

**제약/바이오 특화 사례**

> 출처: [Milvus - Drug Discovery](https://medium.com/vector-database/milvus-in-action-chemical-structure-similarity-search-33130767162a)

- 화학 구조 유사도 검색 (RDKit + Milvus)
- Tanimoto/Jaccard 거리 지원
- Morgan fingerprints 기반 화합물 검색
- 수십억 화합물 라이브러리 검색 가능

**단점 및 실제 프로덕션 이슈**

> 출처: [Milvus Benchmark Report](https://milvus.io/docs/benchmark.md)

| 이슈 | 상세 |
|------|------|
| **운영 복잡도** | 설치/운영에 전문성 필요 |
| **인덱스 빌드 시간** | 100GB 데이터셋 ~5시간 (20코어) |
| **소규모 오버스펙** | 100만건 이하에서 Standalone이 Cluster보다 빠름 |
| **높은 차원에서 성능** | 고차원 임베딩에서 RPS/지연 열세 |

---

### 4. Weaviate

**기본 정보**
- 개발 언어: Go
- 라이선스: BSD-3-Clause
- 특징: 벡터 + Knowledge Graph 하이브리드

**장점**
- GraphQL API
- 하이브리드 검색 (벡터 + 키워드)
- 내장 임베딩 모델

**Healthsearch 데모 (의료/건강 관련)**

> 출처: [Weaviate Healthsearch Demo](https://weaviate.io/blog/healthsearch-demo)

- "I need to sleep better" → 관련 보충제 검색
- 리뷰 텍스트 시맨틱 검색
- 비구조화된 건강 데이터 검색에 적합

**단점**

> 출처: [Vector DB Comparison 2025](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)

| 이슈 | 상세 |
|------|------|
| **리소스 사용량** | 대규모에서 메모리/컴퓨트 과다 |
| **50M 초과 시** | 용량 계획 필수 |
| **순수 벡터 검색** | 벤치마크 최상위권 아님 |

---

### 5. Chroma

**기본 정보**
- 개발 언어: Python → Rust (2025 리라이트)
- 라이선스: Apache 2.0
- 특징: LangChain 친화적

**장점**
- 설치 매우 간단 (`pip install chromadb`)
- 빠른 프로토타이핑
- 2025년 Rust 리라이트로 4x 성능 개선

**단점**

> 출처: [Chroma DB vs Qdrant](https://airbyte.com/data-engineering-resources/chroma-db-vs-qdrant)

| 이슈 | 상세 |
|------|------|
| **스케일링 가이드 부재** | 수평 확장 공식 가이드 없음 |
| **10M 이하 권장** | 대규모 미검증 |
| **엔터프라이즈 지원 없음** | 커뮤니티 의존 |
| **단일 노드 제한** | 분산 데이터 미지원 |

**권장 마이그레이션 경로**: Chroma(프로토타입) → Qdrant(프로덕션)

---

## 의료/바이오 도메인 특화 사례

### PubMed 시맨틱 검색 구현 사례

| 프로젝트 | Vector DB | 임베딩 모델 | 출처 |
|----------|-----------|-------------|------|
| PubMed Central Semantic Search | **Qdrant** | Sentence Transformers | [GitHub](https://github.com/ggruber193/pubmed-central-semantic-search) |
| Medical RAG (BioMistral) | **Qdrant** | PubMedBERT | [GitHub](https://github.com/AIAnytime/Medical-RAG-using-Bio-Mistral-7B) |
| LLM PubMed Knowledge Base | **PostgreSQL** | AWS Bedrock | [Dabble of DevOps](https://www.dabbleofdevops.com/blog/using-llms-to-query-pubmed-knowledgebases) |
| MedGraph | Knowledge Graph | Node2vec | [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9627348/) |

### Healthcare RAG 구현 사례

> 출처: [Qdrant Healthcare RAG](https://medium.com/@kundan.iitk/building-a-healthcare-chatbot-with-qwen-2-and-qdrant-abc0432f3c8c), [Multimodal Healthcare](https://medium.com/@pragnesh.nprajapati/building-a-multimodal-rag-application-using-qdrant-and-gemini-for-enhanced-healthcare-diagnostics-853271ad6367)

| 사례 | 설명 |
|------|------|
| Healthcare Chatbot | Qwen-2 + Qdrant, 환자 이력/리소스 검색 |
| Multimodal Diagnostics | 텍스트 + 의료 이미지 통합 검색 |
| Radiology AI | GPT-4o + Qdrant, 의료 리포트 + 이미지 분석 |

### 제약/신약 개발 사례

> 출처: [Milvus Drug Discovery](https://medium.com/vector-database/milvus-in-action-chemical-structure-similarity-search-33130767162a)

| 사례 | Vector DB | 설명 |
|------|-----------|------|
| 화합물 유사도 검색 | **Milvus** | RDKit + Morgan fingerprints |
| 분자 구조 검색 | **Milvus** | SMILES 포맷, Tanimoto 거리 |

---

## 비교 요약표 (객관적)

| DB | 규모 | 의료/바이오 사례 | 장점 | 단점 | 프로덕션 이슈 |
|----|------|-----------------|------|------|--------------|
| **pgvector** | ~1M (단독) | PostgreSQL 기반 사례 | SQL 통합, 운영 단순 | 스케일 한계, 수평 확장 어려움 | 10M+ 성능 저하 |
| **pgvector+scale** | ~50M | - | 성능 개선 | AWS RDS 미지원 | pgvectorscale 별도 설치 |
| **Qdrant** | ~수백만 | PubMed 검색, Healthcare RAG | 필터링 강점, Rust 성능 | 정적 샤딩 | 인덱싱 지연 사례 |
| **Milvus** | 수십억 | **제약/신약 특화** | 분산, GPU, 화합물 검색 | 운영 복잡 | 인덱스 빌드 장시간 |
| **Weaviate** | ~50M | Healthsearch 데모 | 하이브리드 검색 | 리소스 과다 | 대규모 용량 계획 필요 |
| **Chroma** | ~10M | - | 빠른 시작 | 스케일 미검증 | 프로덕션 부적합 |

---

## 암 논문 챗봇에 "바이오 특화" Vector DB가 필요한가?

### Milvus "바이오 특화"의 실체

Milvus가 바이오 특화라고 하는 이유는 **Tanimoto/Jaccard 거리 함수**를 네이티브 지원하기 때문.

```
일반 텍스트 RAG:
텍스트 → [임베딩 모델] → 벡터(768D) → Cosine 유사도 → 모든 DB 가능

화합물/신약 검색:
분자구조 → [RDKit] → 화학 지문(비트 벡터) → Tanimoto 거리 → Milvus 필요
```

| 검색 타입 | 데이터 | 거리 함수 | 지원 DB |
|----------|--------|----------|---------|
| 텍스트 검색 | 연속 실수 벡터 | Cosine, L2 | **모든 DB** |
| **화합물 검색** | 이진 비트 벡터 | **Tanimoto** | **Milvus만** |

### 암 논문 챗봇에서 검색할 대상

| 검색 대상 | 데이터 타입 | 필요 기능 |
|----------|------------|----------|
| 논문 제목/초록 | 텍스트 | Cosine → **일반 DB 가능** |
| 약물명 (pembrolizumab 등) | 텍스트 | Cosine → **일반 DB 가능** |
| 유전자/변이 (EGFR, BRCA1) | 텍스트 | Cosine → **일반 DB 가능** |
| 저자, 저널, 날짜 | 메타데이터 | SQL 필터링 |
| **화합물 구조 유사도** | 화학 지문 | Tanimoto → **Milvus 필요** |

### 결론: 암 논문 챗봇에는 바이오 특화 불필요

```
우리 프로젝트 (논문 기반 암 전문 Q&A):

바이오 특화 Vector DB (Milvus Tanimoto) → ❌ 불필요
의료 임베딩 모델 (PubMedBERT 등)      → ✅ 중요
하이브리드 검색 (벡터 + 키워드)        → ✅ 중요
메타데이터 필터링                      → ✅ 중요
```

**Milvus 바이오 특화가 필요한 경우:**
- 신약 개발 플랫폼 (화합물 구조 검색)
- 화합물 라이브러리 검색
- 분자 구조 기반 약물 발굴

**우리 프로젝트에서 더 중요한 것:**

| 우선순위 | 항목 | 이유 |
|----------|------|------|
| 1 | **의료 임베딩 모델** | "EGFR" = "Epidermal Growth Factor Receptor" 인식 |
| 2 | **하이브리드 검색** | 정확한 유전자명 + 의미 검색 동시 |
| 3 | **메타데이터 필터링** | 출판년도, 암 종류, 연구 타입 필터 |
| 4 | Vector DB 선택 | 위 3개가 더 중요, DB는 대부분 가능 |

---

## 벡터 데이터 규모 이해하기

### 논문 수 ≠ 벡터 수

논문은 **청킹(Chunking)**을 거쳐 여러 개의 벡터로 변환됩니다.

```
논문 → 청킹 → 벡터화

예: 50,000 논문 × 20 청크 = 1,000,000 벡터
```

**청킹이 필요한 이유:**
1. 임베딩 모델 토큰 제한 (PubMedBERT: 512, OpenAI: 8,192)
2. 검색 정확도 (논문 전체보다 섹션별 검색이 정확)

### 청킹 전략별 벡터 수

| 청킹 전략 | 논문당 청크 수 | 50,000 논문 → 벡터 수 |
|-----------|----------------|----------------------|
| 논문 전체 (비권장) | 1 | 50,000 |
| 섹션별 (Abstract, Methods 등) | 5~8 | 250,000~400,000 |
| 고정 토큰 (512 토큰) | 15~30 | 750,000~1,500,000 |
| 문단별 + 오버랩 | 30~50 | 1,500,000~2,500,000 |

### 업계 규모 기준

**핵심 공식: 규모 = 벡터 수 × 차원 수**

| 규모 | 벡터 수 | 예시 | 인프라 특성 |
|------|---------|------|-------------|
| **소규모** | < 100K (10만) | 사내 문서, 소규모 FAQ | 단일 서버, 인메모리 가능 |
| **중규모** | 100K ~ 10M (1천만) | 이커머스 상품, 뉴스 아카이브 | 단일 서버, 디스크 인덱스 |
| **대규모** | 10M ~ 100M (1억) | 학술 논문 전체, 대형 플랫폼 | 분산 클러스터 필요 |
| **초대규모** | > 100M (1억+) | 검색엔진, 소셜미디어 | 샤딩, 복제 필수 |

### 논문 수 → 실제 규모 환산

| 논문 수 | 벡터 수 (×20 청크) | 규모 분류 | 권장 DB |
|---------|-------------------|----------|---------|
| 5만 건 | ~100만 (1M) | 중규모 | pgvector, Qdrant |
| 10만 건 | ~200만 (2M) | 중규모 | pgvector, Qdrant |
| 50만 건 | ~1,000만 (10M) | 중규모/대규모 경계 | Qdrant, Milvus |
| **100만 건** | **~2,000만 (20M)** | **대규모** | Qdrant, Milvus, Weaviate |
| **500만 건** | **~1억 (100M)** | **초대규모** | Milvus, Pinecone |

### 스토리지 계산

```
벡터 스토리지 = 벡터 수 × 차원 수 × 4바이트(float32)

예: 100만 벡터 × 1536D × 4B = ~6GB (순수 벡터)
+ 인덱스 오버헤드 (1.5~3배) = ~10~18GB 실제 필요
```

---

## 대규모(10M+ 벡터) 벡터 DB 3종 심층 비교

### 1. Qdrant

```
언어: Rust
라이선스: Apache 2.0 (오픈소스)
```

**강점**
- 빠른 성능 (Rust 기반, 메모리 효율적)
- 풍부한 필터링 (숫자, 텍스트, 지리 등)
- 간단한 API, 빠른 러닝커브
- 단일 노드에서도 10M+ 처리 가능
- 하이브리드 검색 지원 (sparse + dense)

**약점**
- 분산 클러스터가 상대적으로 늦게 추가됨
- Milvus 대비 커뮤니티 규모 작음

**적합한 경우**
- 중규모→대규모 성장 예상
- 운영 복잡도 낮추고 싶을 때
- 메타데이터 필터링 중요할 때

---

### 2. Milvus

```
언어: Go + C++
라이선스: Apache 2.0 (오픈소스)
관리형: Zilliz Cloud
```

**강점**
- 초대규모 설계 (100M+ 검증됨)
- 다양한 인덱스 (IVF, HNSW, DiskANN 등)
- GPU 가속 지원
- 성숙한 분산 아키텍처
- 가장 큰 오픈소스 벡터 DB 커뮤니티

**약점**
- 복잡한 아키텍처 (etcd, MinIO, Pulsar 의존)
- 운영 난이도 높음 (쿠버네티스 권장)
- 소규모에선 오버엔지니어링

**적합한 경우**
- 확실히 대규모 (10M+) 시작
- 쿠버네티스 인프라 있음
- GPU 활용 계획 있음

---

### 3. Weaviate

```
언어: Go
라이선스: BSD-3 (오픈소스)
관리형: Weaviate Cloud
```

**강점**
- GraphQL API (프론트엔드 친화적)
- 내장 벡터라이저 (모델 자동 연동)
- 멀티모달 검색 (이미지, 텍스트 동시)
- 하이브리드 검색 (BM25 + 벡터) 기본 내장
- 스키마 기반 데이터 모델링

**약점**
- 순수 벡터 검색 성능은 Qdrant/Milvus보다 낮음
- 메모리 사용량 높음
- 커스터마이징 유연성 낮음

**적합한 경우**
- 멀티모달 검색 필요
- GraphQL 선호
- 빠른 프로토타이핑

---

### 대규모 3종 요약 비교

| 항목 | Qdrant | Milvus | Weaviate |
|------|--------|--------|----------|
| **성능** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **운영 난이도** | 쉬움 | 어려움 | 중간 |
| **분산 확장** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **하이브리드 검색** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **필터링** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **커뮤니티** | 중간 | 큼 | 중간 |
| **러닝커브** | 낮음 | 높음 | 중간 |

---

## 우리 프로젝트 고려사항

### 현재 상황
- **테스트**: 10만 건 (벡터 ~200만)
- **최대 목표**: 500만 건 (벡터 ~1억)
- 도메인: 의료/바이오 (암 논문)
- 단계: MVP/스파이크

### 규모별 우리 프로젝트 위치

```
┌─────────────────────────────────────────────────────────────┐
│  소규모     │  중규모        │  대규모       │ 초대규모     │
│  <100K     │  100K~10M     │  10M~100M    │  >100M      │
│            │  ↑테스트(2M)   │              │  ↑최대(100M) │
└─────────────────────────────────────────────────────────────┘
```

### 선택 시 고려할 질문들

**1. 인프라 복잡도 vs 성능**
- PostgreSQL 하나로 통합할 것인가? (pgvector)
- 별도 Vector DB 운영할 여력이 있는가? (Qdrant, Milvus)

**2. 스케일 전망**
- 10만건(테스트)에서 멈출 것인가?
- 500만건(최대)까지 확장 가능성이 있는가?

**3. 의료 도메인 요구사항**
- 단순 논문 검색인가? → 대부분 DB 가능
- 화합물/분자 구조 검색이 필요한가? → Milvus 고려
- 멀티모달 (이미지+텍스트) 필요한가? → Qdrant/Weaviate 고려

**4. 팀 역량**
- PostgreSQL 운영 경험이 있는가?
- 별도 인프라 운영 가능한가?

### 우리 프로젝트 규모별 권장

| 단계 | 논문 수 | 벡터 수 | 규모 | 권장 |
|------|---------|---------|------|------|
| **테스트** | 10만 | ~200만 | 중규모 | pgvector, Qdrant |
| **초기 운영** | 50만 | ~1,000만 | 중/대규모 경계 | Qdrant |
| **최대 확장** | 500만 | ~1억 | 초대규모 | Milvus, Qdrant 클러스터 |

**결론**: 500만 건까지 확장 가능성을 고려하면, **처음부터 Qdrant 또는 Milvus**로 시작하는 것이 마이그레이션 비용을 줄일 수 있음.

---

## 옵션별 트레이드오프

### Option A: pgvector (단독)
```
장점: 인프라 단순, SQL 통합, 빠른 시작
단점: 10M+ 성능 저하 리스크, 수평 확장 어려움
적합: MVP 빠른 검증, 소규모 유지 예상
```

### Option B: Qdrant
```
장점: 의료 RAG 사례 다수, 필터링 강점, Docker 배포
단점: 별도 인프라, PostgreSQL과 동기화 필요
적합: 복잡한 메타데이터 필터링, 중규모 확장 예상
```

### Option C: Milvus
```
장점: 제약/바이오 특화, 대규모 확장, 화합물 검색
단점: 운영 복잡도 높음, 소규모 오버스펙
적합: 수백만건 이상 확장, 화합물 검색 필요
```

### Option D: pgvector → Qdrant 마이그레이션 전략
```
1단계: pgvector로 MVP 빠르게
2단계: 스케일 이슈 발생 시 Qdrant로 전환
리스크: 마이그레이션 비용
```

---

## 다음 단계 (팀 결정 필요)

- [ ] 인프라 복잡도 허용 범위 논의
- [ ] 스케일 전망 확정
- [ ] 화합물/분자 검색 필요 여부 확인
- [ ] 프로토타입으로 2-3개 후보 직접 테스트

---

## 참고 자료

### 벤치마크 비판/독립 평가
- [Milvus: Benchmarks Lie](https://milvus.io/blog/benchmarks-lie-vector-dbs-deserve-a-real-test.md)
- [benchANT: DeWitt Clause](https://benchant.com/blog/vectordb-de-witt)
- [VDBBench](https://milvus.io/blog/vdbbench-1-0-benchmarking-with-your-real-world-production-workloads.md)

### 프로덕션 이슈
- [The Case Against pgvector](https://alex-jacobs.com/posts/the-case-against-pgvector/)
- [Qdrant Troubleshooting](https://qdrant.tech/documentation/guides/common-errors/)
- [Qdrant GitHub Issues](https://github.com/qdrant/qdrant/issues)

### 의료/바이오 사례
- [Medical RAG with BioMistral](https://github.com/AIAnytime/Medical-RAG-using-Bio-Mistral-7B)
- [PubMed Semantic Search](https://github.com/ggruber193/pubmed-central-semantic-search)
- [Milvus Drug Discovery](https://medium.com/vector-database/milvus-in-action-chemical-structure-similarity-search-33130767162a)
- [Weaviate Healthsearch](https://weaviate.io/blog/healthsearch-demo)

### 비교 분석
- [Vector DB Comparison 2025 - LiquidMetal AI](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)
- [Chroma vs Milvus vs Qdrant](https://agixtech.com/chroma-vs-milvus-vs-qdrant-vector-db-comparison/)
