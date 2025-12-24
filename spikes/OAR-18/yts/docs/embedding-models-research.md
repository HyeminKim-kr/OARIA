# 임베딩 모델 리서치: 암/종양학 논문 RAG용

> **목적**: 암 논문 RAG 시스템에 적합한 임베딩 모델 선정
>
> **작성일**: 2025-12-23
>
> **핵심 질문**: 일반 모델 vs 의료 특화 모델, 어떤 것이 더 나은가?

---

## TL;DR (결론 먼저)

| 상황 | 권장 모델 | 이유 |
|------|----------|------|
| **빠른 프로토타입** | OpenAI text-embedding-3-small | 쉬운 구현, 우수한 성능 |
| **비용 효율 + 성능** | BGE-M3 또는 E5-large-v2 | 오픈소스, 상용 수준 성능 |
| **의료 도메인 최적화** | MedCPT 또는 S-PubMedBERT | PubMed 특화, 벤치마크 검증 |
| **암 논문 RAG (권장)** | **MedCPT → OpenAI 비교 테스트** | 크로스체크 필수 |

> ⚠️ **중요 발견**: 일부 연구에서 **일반 모델이 의료 특화 모델보다 나은 성능**을 보임. 반드시 우리 데이터로 테스트 필요!

---

## 벤치마크 이해하기

### 주요 벤치마크

| 벤치마크 | 설명 | 중요 지표 |
|----------|------|----------|
| **MTEB** | Massive Text Embedding Benchmark, 56개 데이터셋 | Retrieval 점수 (RAG용) |
| **BEIR** | 검색 특화, 18개 다양한 도메인 | nDCG@10 |
| **MedTEB** | 의료 특화 (2024 신규), 51개 태스크 | 의료 검색/분류 |

### MTEB Retrieval 순위 (2025)

| 순위 | 모델 | Retrieval 점수 | 비고 |
|------|------|---------------|------|
| 1 | NV-Embed-v2 | 62.7% | NVIDIA, 7B 파라미터 |
| 2 | SFR-Embedding-Mistral | 59.0% | Salesforce |
| 3 | e5-mistral-7b-instruct | 56.9% | 오픈소스 |
| 4 | **OpenAI 3-Large** | 55.4% | 상용, 사용 편의성 ⭐ |
| 5 | Cohere English v3 | 55.0% | 상용 |
| - | **BGE-M3** | ~54% | 오픈소스, 다기능 ⭐ |

---

## 일반 임베딩 모델 비교

### 1. OpenAI text-embedding-3

| 모델 | 차원 | 토큰 한도 | 비용 (1M 토큰) | 특징 |
|------|------|----------|---------------|------|
| text-embedding-3-small | 1536 | 8191 | $0.02 | 비용 효율 |
| text-embedding-3-large | 3072 | 8191 | $0.13 | 최고 성능 |

**장점**:
- 가변 차원 (3072 → 256 축소 가능, 성능 유지)
- 다국어 지원
- API 안정성

**단점**:
- 비용 (대규모 시)
- 의료 도메인 특화 아님

```python
from openai import OpenAI

client = OpenAI()
response = client.embeddings.create(
    model="text-embedding-3-small",
    input="EGFR mutation in non-small cell lung cancer"
)
embedding = response.data[0].embedding
```

---

### 2. BGE-M3 (BAAI)

| 항목 | 값 |
|------|-----|
| 차원 | 1024 |
| 토큰 한도 | 8192 |
| 라이선스 | Apache 2.0 (상용 가능) |
| 비용 | 무료 (셀프 호스팅) |

**장점**:
- **3가지 검색 방식**: Dense, Sparse (BM25 대체), Multi-vector
- 100+ 언어 지원
- MTEB 84.7% (STS 태스크)

**단점**:
- 셀프 호스팅 필요
- 의료 도메인 특화 아님

```python
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
embeddings = model.encode(["EGFR mutation treatment"])['dense_vecs']
```

---

### 3. E5 시리즈 (Microsoft)

| 모델 | 차원 | 특징 |
|------|------|------|
| e5-small-v2 | 384 | 빠름, 저지연 (<30ms) |
| e5-large-v2 | 1024 | 균형 |
| e5-mistral-7b-instruct | 4096 | 최고 성능, 무거움 |

**장점**:
- Top-5 정확도 100% (일부 태스크)
- 다양한 크기 선택

---

### 4. Cohere Embed v3/v4

| 항목 | 값 |
|------|-----|
| MTEB | 64.6% |
| 토큰 한도 | 8192 |
| 비용 | $0.12 / 1M 토큰 |

**장점**:
- 100+ 언어
- Long-context 지원

---

## 의료/생명과학 특화 모델

### 1. MedCPT ⭐ 의료 RAG 추천

**BEIR 벤치마크에서 Google GTR-XXL (4.8B), OpenAI cpt-text-XL (175B)보다 우수!**

| 항목 | 값 |
|------|-----|
| 학습 데이터 | 2.55억 PubMed 쿼리-논문 쌍 (실제 클릭 로그) |
| 구조 | Retriever + Re-ranker 통합 |
| 특화 | 생물의학 정보 검색 |

**왜 강력한가?**
- 실제 PubMed 사용자 클릭 데이터로 학습
- Zero-shot 생물의학 검색에 최적화
- 검색 + 리랭킹 통합

```python
from transformers import AutoModel, AutoTokenizer

model = AutoModel.from_pretrained("ncbi/MedCPT-Query-Encoder")
tokenizer = AutoTokenizer.from_pretrained("ncbi/MedCPT-Query-Encoder")

# 쿼리 인코딩
query = "What is the treatment for EGFR-mutated lung cancer?"
inputs = tokenizer(query, return_tensors="pt")
query_embedding = model(**inputs).last_hidden_state[:, 0, :]
```

**HuggingFace**: [ncbi/MedCPT-Query-Encoder](https://huggingface.co/ncbi/MedCPT-Query-Encoder)

---

### 2. PubMedBERT / S-PubMedBERT

| 모델 | 차원 | 특징 |
|------|------|------|
| PubMedBERT | 768 | PubMed 전용 사전학습 |
| S-PubMedBERT | 768 | + Sentence Transformer 파인튜닝 |
| pubmedbert-base-embeddings | 768 | 임베딩 최적화 버전 |

> ⚠️ **흥미로운 발견**: S-PubMedBERT가 PubMedBERT보다 **29% 더 정확**. Sentence Transformer 파인튜닝이 핵심!

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('NeuML/pubmedbert-base-embeddings')
embeddings = model.encode(["EGFR mutation treatment efficacy"])
```

**HuggingFace**: [NeuML/pubmedbert-base-embeddings](https://huggingface.co/NeuML/pubmedbert-base-embeddings)

---

### 3. BioLORD-2023

| 항목 | 값 |
|------|-----|
| 기반 | UMLS 지식 그래프 + LLM |
| 특화 | 생물의학 + 임상 도메인 |
| 언어 | 영어 + 50개 언어 (다국어 버전) |

**특징**:
- Contrastive Learning + Self-Distillation
- UMLS 의학 용어 체계 활용
- 의료 개념 매핑에 강함

---

### 4. 기타 의료 모델

| 모델 | 특화 | 비고 |
|------|------|------|
| BioBERT | 생물의학 문헌 | "mRNA", "targeted therapy" 정확 처리 |
| ClinicalBERT | 임상 노트 | EHR, 퇴원 기록 |
| SciBERT | 과학 문헌 | CS + 생물의학 |
| BioGPT | 생물의학 생성 | GPT 기반 |

---

## 일반 모델 vs 의료 특화 모델: 뜻밖의 결과

### 2024년 임상 검색 벤치마크 결과

| 순위 | 모델 | 유형 | 정확도 |
|------|------|------|--------|
| 1 | jina-embeddings-v2-base-en | **일반** | 최고 |
| 2 | e5-small-v2 | **일반** | 상위 |
| 3 | e5-large-v2 | **일반** | 상위 |
| 4 | ClinicalBERT | 의료 | - |
| 5 | CORe-clinical-outcome-BioBERT | 의료 | - |

> 📊 **결론**: "연구진은 의료 특화 모델이 더 나을 것으로 예상했으나, **상위 3개 모두 일반 모델**이었다."

### 왜 이런 결과가?

1. **학습 데이터 규모**: 일반 모델이 훨씬 큰 데이터로 학습
2. **Sentence Transformer**: 일반 데이터로 파인튜닝된 모델이 의미 검색에 강함
3. **의료 특화 모델 한계**:
   - 학습 데이터 적음
   - 벤치마크 부족 (평가 어려움)
   - Sentence Transformer 미적용 버전 다수

---

## 암/종양학 RAG에 대한 권장사항

### 우리 상황

| 요소 | 내용 |
|------|------|
| 도메인 | 암/종양학 (Oncology) |
| 데이터 소스 | Europe PMC (Open Access 논문) |
| 언어 | 영어 |
| 검색 대상 | 논문 섹션 (Abstract, Results, Discussion 등) |

### 추천 전략: 크로스체크 필수!

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: 프로토타입                                         │
│  → OpenAI text-embedding-3-small (빠른 구현)                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: 의료 특화 모델 테스트                               │
│  → MedCPT (PubMed 특화)                                     │
│  → pubmedbert-base-embeddings                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: 크로스체크 비교 평가                                │
│  → 동일 쿼리셋으로 Recall@10, nDCG 비교                      │
│  → 암 관련 쿼리 10-20개 수동 평가                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: 최종 선정                                          │
│  → 성능 + 비용 + 운영 복잡도 종합 판단                        │
└─────────────────────────────────────────────────────────────┘
```

### 평가 기준

| 지표 | 설명 | 목표 |
|------|------|------|
| Recall@10 | 상위 10개 중 관련 청크 비율 | > 80% |
| nDCG@10 | 순위 품질 | > 0.7 |
| Latency | 임베딩 생성 시간 | < 100ms |
| 비용 | 월간 임베딩 비용 | 예산 내 |

### 테스트 쿼리 예시 (암/종양학)

```python
test_queries = [
    "EGFR mutation treatment in non-small cell lung cancer",
    "Immunotherapy response rate in melanoma",
    "BRCA1 mutation and breast cancer prognosis",
    "PD-L1 expression and checkpoint inhibitor efficacy",
    "Chemotherapy resistance mechanisms in ovarian cancer",
    "CAR-T therapy side effects in leukemia",
    "Tumor microenvironment and metastasis",
    "Liquid biopsy for early cancer detection",
    "Targeted therapy for HER2-positive breast cancer",
    "Radiation therapy complications in prostate cancer"
]
```

---

## 비용 비교

### 10만 논문 임베딩 기준 (평균 25 청크/논문)

| 모델 | 청크당 토큰 | 총 토큰 | 비용 |
|------|-----------|--------|------|
| OpenAI 3-small | ~250 | 625M | **~$12.50** |
| OpenAI 3-large | ~250 | 625M | **~$81.25** |
| Cohere v3 | ~250 | 625M | **~$75** |
| BGE-M3 (셀프호스팅) | - | - | **GPU 비용만** |
| MedCPT (셀프호스팅) | - | - | **GPU 비용만** |

> 💡 프로토타입은 OpenAI, 프로덕션은 셀프호스팅 검토

---

## 결론 및 다음 단계

### 최종 권장

| 단계 | 모델 | 이유 |
|------|------|------|
| MVP | OpenAI text-embedding-3-small | 빠른 구현, 검증된 품질 |
| 비교 대상 | MedCPT | PubMed 특화, BEIR 검증 |
| 대안 | BGE-M3 | 오픈소스, 비용 효율 |

### 다음 단계

- [ ] OpenAI 임베딩으로 프로토타입 구현
- [ ] 테스트 쿼리셋 구축 (암 관련 10-20개)
- [ ] MedCPT 셀프호스팅 환경 구축
- [ ] 크로스체크 비교 평가 수행
- [ ] 결과 기반 최종 모델 선정

---

## 참고 자료

### 일반 임베딩
- [Pinecone - Choosing an Embedding Model](https://www.pinecone.io/learn/series/rag/embedding-models-rundown/)
- [ZenML - 9 Best Embedding Models for RAG](https://www.zenml.io/blog/best-embedding-models-for-rag)
- [AIMultiple - Open Source Embedding Models Benchmark](https://research.aimultiple.com/open-source-embedding-models/)

### 의료 특화
- [MedCPT - Contrastive Pre-trained Transformers](https://www.marktechpost.com/2023/11/11/are-you-doing-retrieval-augmented-generation-rag-for-biomedicine-meet-medcpt/)
- [NeuML - PubMedBERT Embeddings](https://huggingface.co/NeuML/pubmedbert-base-embeddings)
- [arXiv - Domain Specification of Embedding Models in Medicine](https://arxiv.org/html/2507.19407v1)
- [arXiv - Generalist vs Specialized Embedding Models](https://arxiv.org/html/2401.01943v2)

### 벤치마크
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [BEIR Benchmark](https://github.com/beir-cellar/beir)
