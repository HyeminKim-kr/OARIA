# 임베딩 모델 결정

> **결정**: OpenAI text-embedding-3-small
>
> **작성일**: 2025-12-30
>
> **상태**: 확정 (MVP)

---

## TL;DR

| 항목 | 결정 |
|------|------|
| **모델** | OpenAI text-embedding-3-small |
| **차원** | 1536 |
| **비용** | ~$0.02 / 1M tokens |
| **버전 문자열** | `openai:text-embedding-3-small:v1` |

---

## 결정 근거

### 선택 이유

| 기준 | 평가 |
|------|------|
| 개발 속도 | ✅ API 호출만으로 즉시 사용 |
| 인프라 부담 | ✅ 없음 (셀프 호스팅 불필요) |
| 비용 | ✅ 저렴 (~$0.02 / 1M tokens) |
| 성능 | ✅ MTEB 벤치마크 상위권 |
| 교체 용이성 | ✅ BYOV 구조로 나중에 교체 가능 |

### MVP 우선순위

1. **빠른 프로토타이핑** - API 호출로 즉시 사용
2. **인프라 복잡도 최소화** - GPU 서버 불필요
3. **검증된 성능** - 범용 임베딩으로 기본 품질 보장

---

## 고려했던 대안

| 모델 | 장점 | 단점 | 채택 여부 |
|------|------|------|----------|
| **text-embedding-3-small** | API 간편, 저렴, 좋은 성능 | 의료 특화 X | ✅ 채택 |
| text-embedding-3-large | 더 높은 성능 | 비용 6배 | ❌ |
| MedCPT | 의료 논문 특화, 무료 | GPU 셀프호스팅 필요 | ❌ (추후 비교) |
| PubMedBERT | PubMed 학습 | 768차원, 셀프호스팅 | ❌ |
| Cohere embed-v3 | 다국어, 좋은 성능 | 비용 | ❌ |

---

## 추후 스파이크 계획

### 목표
의료 도메인 특화 모델(MedCPT)과 범용 모델(OpenAI) 검색 품질 비교

### 비교 항목
- 동일 쿼리셋으로 Recall@K 측정
- 의료 용어 검색 정확도
- 비용 대비 성능 분석

### 예상 시점
- MVP 검증 후 진행
- 데이터 충분히 쌓인 후 (논문 1,000편+)

---

## 구현

### 버전 관리

```python
EMBEDDING_VERSION = "openai:text-embedding-3-small:v1"
```

모델 변경 시:
1. 새 컬렉션 생성 (`PaperChunk_v2`)
2. 새 임베딩으로 전체 재적재
3. 검증 후 이전 컬렉션 삭제

### 사용 예시

```python
from src.embeddings import EmbeddingClient

client = EmbeddingClient()
embedding = client.embed_text("lung cancer immunotherapy treatment")
# → [0.12, -0.34, 0.56, ...] (1536차원)
```

---

## 비용 추정

| 규모 | 예상 청크 수 | 토큰 수 (추정) | 비용 |
|------|-------------|---------------|------|
| 1,000 논문 | ~25,000 청크 | ~25M tokens | ~$0.50 |
| 10,000 논문 | ~250,000 청크 | ~250M tokens | ~$5.00 |
| 100,000 논문 | ~2,500,000 청크 | ~2.5B tokens | ~$50.00 |

> 쿼리 임베딩 비용은 미미함 (쿼리당 ~100 tokens)

---

## 참고

- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [MedCPT Paper](https://arxiv.org/abs/2307.00589)
