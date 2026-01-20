# OARIA Functional Requirements Specification (FRS)
## Oncology AI Research Intelligence Assistant

> **Author**: 김혜민 (Hyemin Kim)
> **Version**: 1.0
> **Last Updated**: 2025-12-31
> **For**: PhD Mentors & Stakeholders

---

## 목차 (Table of Contents)

1. [프로젝트 개요 (Project Overview)](#1-프로젝트-개요-project-overview)
2. [핵심 기능 설명 (Core Features)](#2-핵심-기능-설명-core-features)
3. [데이터 수집 전략 (Data Collection Strategy)](#3-데이터-수집-전략-data-collection-strategy)
4. [텍스트 처리 전략 (Text Processing Strategy)](#4-텍스트-처리-전략-text-processing-strategy)
5. [검색 시스템 (Search System)](#5-검색-시스템-search-system)
6. [메타데이터 전략 (Metadata Strategy)](#6-메타데이터-전략-metadata-strategy)
7. [품질 보장 시스템 (Quality Assurance - 3 Gates)](#7-품질-보장-시스템-quality-assurance---3-gates)
8. [기술 스택 정당화 (Technology Justification)](#8-기술-스택-정당화-technology-justification)
9. [성능 목표 (Performance Targets)](#9-성능-목표-performance-targets)

---

## 1. 프로젝트 개요 (Project Overview)

### 1.1 OARIA가 무엇인가요?

**OARIA**는 암 연구자들을 위한 AI 연구 도우미입니다.

**쉽게 설명하면:**
- 연구자가 "EGFR 변이가 폐암 치료에 어떤 영향을 미치나요?" 같은 질문을 하면
- OARIA가 수백 개의 논문을 검색하고
- 관련된 증거를 찾아서
- **출처를 명시한 답변**을 제공합니다

**핵심 가치:**
1. ✅ **증거 기반 답변**: 모든 답변에 논문 인용 포함
2. ✅ **환각 방지**: 논문에 없는 내용은 답변하지 않음
3. ✅ **도메인 특화**: 암 연구에만 집중 (다른 분야 질문은 거절)

### 1.2 왜 이 시스템이 필요한가요?

| 기존 방식 | OARIA |
|-----------|-------|
| ChatGPT에 질문 → 출처 불명확, 환각 가능 | 논문 기반 답변 → 출처 명확 |
| PubMed 검색 → 수백 개 논문 직접 읽어야 함 | 관련 부분만 추출해서 요약 |
| 검색어 정확히 일치해야 검색됨 | 의미 기반 검색 (유사 표현도 찾음) |

### 1.3 일반 ChatGPT와 뭐가 다른가요?

```
[일반 ChatGPT]
사용자: EGFR 변이 치료법은?
ChatGPT: EGFR 변이 치료에는 gefitinib, erlotinib 등이 있습니다.
         → 출처 없음, 최신 정보인지 불확실

[OARIA]
사용자: EGFR 변이 치료법은?
OARIA: EGFR 변이 폐암 치료에는 1세대 TKI (gefitinib, erlotinib)가
       사용되지만, T790M 내성 발생 시 osimertinib이 효과적입니다 [1][2].

       [1] Smith et al., Nature Medicine, 2023
       [2] Kim et al., JCO, 2024
       → 모든 주장에 논문 출처 명시
```

---

## 2. 핵심 기능 설명 (Core Features)

### 2.1 Feature 목록

| Feature ID | 이름 | 설명 | 상태 |
|------------|------|------|------|
| F-01 | Domain Classifier | 질문이 암 관련인지 판별 | 🔄 진행 예정 |
| F-02 | Paper Crawler | 논문 자동 수집 | ✅ 완료 (975편) |
| F-03 | Evidence RAG | 논문 기반 답변 생성 | 🔄 진행 중 |
| F-04 | Agent Task Decomposition | 복잡한 질문 분해 | 🔄 진행 예정 |
| F-05 | Retrieval Confidence | 검색 결과 신뢰도 검증 | 🔄 진행 중 |
| F-06 | RAGAS Evaluation | 답변 품질 자동 평가 | 🔄 진행 예정 |

### 2.2 각 Feature 상세 설명

#### F-01: Domain Classifier (Gate 1)
**목적**: 암 연구 관련 질문만 처리

```
예시:
✅ "KRAS 변이 폐암의 예후는?" → 암 관련 → 처리
✅ "면역항암제 부작용은?" → 암 관련 → 처리
❌ "고혈압 약은 뭐가 좋아요?" → 심장내과 → 거절
❌ "날씨가 왜 추워요?" → 비의료 → 거절
```

**거절 메시지 예시:**
> "저는 암 연구 전문 AI입니다. 심장 관련 질문은 심장내과 전문 리소스를 참고해 주세요."

#### F-02: Paper Crawler (완료)
**목적**: 암 관련 논문 자동 수집

**수집 현황 (2025-12-31):**
| 항목 | 값 |
|------|-----|
| 총 논문 수 | 975편 |
| 총 텍스트 크기 | 41.2 MB |
| 평균 논문 길이 | 42,252자 |
| 수집 소스 | PMC (880), medRxiv (70), arXiv (16) |

**왜 이 소스들인가요?**
- **PMC (PubMed Central)**: 정식 출판된 peer-reviewed 논문
- **medRxiv**: 의학 분야 프리프린트 (최신 연구)
- **arXiv**: 컴퓨터과학/수학 분야 (AI+의료 융합 연구)

**중요**: 초록(abstract)만이 아닌 **전체 논문(full-text)**를 수집했습니다!

#### F-03: Evidence RAG
**목적**: 논문에서 증거를 찾아 답변 생성

**RAG가 뭔가요?**
RAG = Retrieval-Augmented Generation (검색 증강 생성)

```
쉽게 설명하면:
1. 사용자 질문 → "EGFR 변이 치료법은?"
2. 검색(Retrieval) → 관련 논문 조각(chunk) 검색
3. 증강(Augmented) → 검색된 내용을 AI에게 전달
4. 생성(Generation) → AI가 출처 기반으로 답변 작성
```

**왜 RAG가 필요한가요?**
| 방식 | 장점 | 단점 |
|------|------|------|
| 일반 LLM | 빠름 | 환각, 출처 없음 |
| RAG | 출처 명확, 환각 감소 | 검색 품질에 의존 |

#### F-04: Agent Task Decomposition
**목적**: 복잡한 질문을 작은 단위로 분해

```
복잡한 질문:
"EGFR 억제제와 면역항암제를 비교해주세요"

분해:
1. EGFR 억제제의 작용 기전은?
2. 면역항암제의 작용 기전은?
3. 각각의 효과와 부작용은?
4. 직접 비교 연구가 있는가?
5. 종합 비교
```

#### F-05: Retrieval Confidence (Gate 2)
**목적**: 검색 결과가 충분한지 확인

**통과 조건:**
- 최소 3개 이상의 관련 논문 발견
- 최고 유사도 점수 ≥ 0.7
- 암 관련 논문 비율 ≥ 80%

**실패 시:**
> "죄송합니다. 해당 질문에 대한 충분한 근거 자료를 찾지 못했습니다.
> 질문을 더 구체화하거나 다른 용어로 시도해 주세요."

#### F-06: RAGAS Evaluation (Gate 3)
**목적**: 생성된 답변의 품질 평가

**평가 지표:**
| 지표 | 설명 | 목표 |
|------|------|------|
| Faithfulness | 답변이 논문 내용에 충실한가? | ≥ 0.85 |
| Answer Relevancy | 답변이 질문에 적절한가? | ≥ 0.80 |

**낮은 점수일 경우:**
> "⚠️ 이 답변은 신뢰도가 낮을 수 있습니다. 원본 논문을 직접 확인하시기 바랍니다."

---

## 3. 데이터 수집 전략 (Data Collection Strategy)

### 3.1 왜 OpenAlex를 사용하나요?

| 비교 항목 | OpenAlex | PubMed |
|-----------|----------|--------|
| 논문 수 | 2.5억+ (전체 학문) | 3,500만 (생명과학만) |
| 암 논문 포함? | ✅ PubMed 전부 포함 | ✅ |
| API 편의성 | ✅ 쉬움, 키 불필요 | ⚠️ 복잡 |
| 메타데이터 | ✅ 풍부 (인용수, 개념 등) | ⚠️ 기본 |

**결론**: OpenAlex가 PubMed의 모든 논문을 포함하면서 더 사용하기 쉽습니다.

### 3.2 왜 Full-Text만 수집하나요?

```
[초록만 사용할 경우]
질문: "T790M 변이의 치료 옵션은?"
초록: "본 연구에서 osimertinib의 효과를 확인했다"
→ 구체적인 치료 방법, 용량, 결과 없음

[Full-Text 사용 시]
논문 본문: "T790M 양성 환자에게 osimertinib 80mg을
          하루 1회 투여했을 때 반응률은 71%였다 (Table 2)"
→ 구체적이고 실용적인 정보 제공 가능
```

**결론**: Full-text가 있어야 연구자에게 실질적으로 유용한 답변이 가능합니다.

### 3.3 수집 소스별 특징

| 소스 | 유형 | 특징 | 비율 |
|------|------|------|------|
| **PMC** | 정식 출판 | Peer-reviewed, 신뢰도 높음 | 88% |
| **medRxiv** | 프리프린트 | 최신 연구, 아직 검토 안됨 | 7% |
| **arXiv** | 프리프린트 | AI+의료 융합 연구 | 2% |

---

## 4. 텍스트 처리 전략 (Text Processing Strategy)

### 4.1 Chunking (청킹) - 논문 쪼개기

**왜 논문을 쪼개야 하나요?**

논문 1편 = 평균 42,000자 (A4 약 20페이지)

```
문제: AI에게 20페이지 전체를 주면?
→ 너무 길어서 처리 불가
→ 관련 없는 부분이 대부분
→ 정확한 위치 파악 어려움

해결: 작은 조각(chunk)으로 나누기
→ 관련 부분만 빠르게 검색
→ 정확한 인용 위치 제공
```

### 4.2 우리의 Chunking 설정

| 설정 | 값 | 이유 |
|------|-----|------|
| **Chunk 크기** | 512 토큰 | BGE-M3 모델의 최적 크기 |
| **Overlap** | 50 토큰 (10%) | 경계에서 정보 손실 방지 |
| **최소 크기** | 100 토큰 | 너무 짧은 조각 제외 |
| **경계** | 문장 단위 | 문장 중간에서 자르지 않음 |

**왜 512 토큰인가요?**

```
토큰이란?
- 단어보다 작은 단위 (영어 기준 1 단어 ≈ 1-2 토큰)
- "immunotherapy" → 약 3 토큰

크기 선택 이유:
- 너무 크면 (1024+): 관련 없는 내용 포함, 검색 정확도 ↓
- 너무 작으면 (128): 맥락 손실, 의미 불명확
- 512: "Goldilocks Zone" - 적당한 맥락 + 정확한 검색
```

**왜 문장 단위로 자르나요?**

```
❌ 나쁜 예 (글자 수로 자름):
"This treatment showed significant improvement in patient survi"
"val rates compared to the control group."
→ "survival"이 두 조각에 나뉨 → 의미 손상

✅ 좋은 예 (문장 단위로 자름):
"This treatment showed significant improvement in patient survival rates compared to the control group."
→ 완전한 문장 유지 → 의미 보존
```

**왜 10% Overlap인가요?**

```
Overlap 없이 자르면:
[Chunk 1] ... EGFR mutations are common in...
[Chunk 2] ...lung cancer patients. Treatment with...

→ "EGFR mutations in lung cancer" 정보가 두 조각에 나뉨

Overlap 있으면:
[Chunk 1] ... EGFR mutations are common in lung cancer patients.
[Chunk 2] in lung cancer patients. Treatment with...

→ 중요 정보가 최소 한 조각에는 완전히 포함됨
```

### 4.3 예상 결과

```
975 논문 × 평균 80 chunks = 약 78,000 chunks
각 chunk = 약 512 토큰 (약 400단어)
```

---

## 5. 검색 시스템 (Search System)

### 5.1 Embedding (임베딩) - 텍스트를 숫자로 변환

**왜 텍스트를 숫자로 바꾸나요?**

```
컴퓨터는 "폐암"과 "lung cancer"가 같은 의미인지 모릅니다.
하지만 숫자로 변환하면:

"폐암" → [0.23, 0.45, 0.12, ...] (1024개 숫자)
"lung cancer" → [0.24, 0.44, 0.13, ...] (비슷한 숫자!)
"심장병" → [0.87, 0.12, 0.56, ...] (다른 숫자)

→ 숫자가 비슷하면 의미가 비슷!
```

### 5.2 우리가 BGE-M3를 선택한 이유

| 특징 | BGE-M3 | PubMedBERT |
|------|--------|------------|
| 도메인 | 범용 (모든 분야) | 의학 전용 |
| 하이브리드 | ✅ Dense + Sparse | ❌ Dense만 |
| 한국어 | ✅ 지원 | ❌ 영어만 |
| 성능 | ✅ 최신 SOTA | ⚠️ 2020년 모델 |

### 5.3 Hybrid Search (하이브리드 검색)

**왜 두 가지 검색을 섞나요?**

```
[Dense Search - 의미 검색]
장점: "폐암" 검색하면 "lung cancer" 논문도 찾음
단점: "EGFR" 검색 시 비슷한 단어와 혼동 가능

[Sparse Search - 키워드 검색]
장점: "EGFR" 정확히 일치하는 것만 찾음
단점: "폐암"과 "lung cancer"를 다른 것으로 인식

[Hybrid Search - 둘 다 사용]
✅ 의미적으로 관련된 논문도 찾고
✅ 정확한 유전자/약물명도 놓치지 않음
```

**실제 예시:**

```
질문: "EGFR mutation in pulmonary malignancy"

Dense Search가 찾는 것:
- "lung cancer EGFR alterations" (의미 유사)
- "폐암 EGFR 변이" (한국어도!)

Sparse Search가 찾는 것:
- "EGFR mutation" (정확히 일치)

Hybrid = 둘 다 찾아서 합침!
```

### 5.4 RRF (Reciprocal Rank Fusion)

**두 검색 결과를 어떻게 합치나요?**

```
Dense 검색 결과:    Sparse 검색 결과:
1. 논문 A          1. 논문 C
2. 논문 B          2. 논문 A
3. 논문 C          3. 논문 D

RRF 공식:
점수 = 1/(rank + 60)

논문 A: 1/(1+60) + 1/(2+60) = 0.033
논문 C: 1/(3+60) + 1/(1+60) = 0.032
논문 B: 1/(2+60) + 0 = 0.016

최종 순위: A > C > B > D
→ 두 검색 모두에서 높은 순위면 더 높은 점수!
```

---

## 6. 메타데이터 전략 (Metadata Strategy)

### 6.1 왜 메타데이터가 중요한가요?

**메타데이터 = 논문에 대한 정보**

```
논문 본문: "EGFR mutation shows response to treatment..."

메타데이터:
- 제목: "EGFR Mutations in Lung Cancer"
- 저자: ["Smith J", "Kim H"]
- 저널: "Nature Medicine"  ← 이게 Nature인지 알아야 함
- 연도: 2024              ← 최신 논문인지 알아야 함
- 인용수: 150             ← 영향력 있는 논문인지 알아야 함
```

### 6.2 저장하는 메타데이터

| 메타데이터 | 용도 |
|------------|------|
| `paper_id` | 논문 고유 식별자 |
| `title` | 인용 시 제목 표시 |
| `authors` | 인용 시 저자 표시 |
| `journal` | 저널명 표시 |
| `journal_tier` | 저널 등급 필터링 |
| `publication_year` | 연도 필터링 |
| `cited_by_count` | 영향력 필터링 |
| `doi` | 논문 링크 제공 |
| `source` | 출처 (PMC/arXiv) 표시 |
| `concepts` | 주제 기반 필터링 |

### 6.3 Journal Tier (저널 등급) 시스템

**왜 저널 등급이 필요한가요?**

```
연구자: "최근 고영향력 저널의 논문만 보고 싶어요"

등급 없이: 모든 논문 다 검색됨
등급 있으면: journal_tier=["tier1", "tier2"] 필터 가능!
```

**등급 분류:**

| 등급 | Impact Factor | 예시 저널 |
|------|---------------|-----------|
| **Tier 1** | IF > 30 | Nature, Cell, NEJM, Lancet, Cancer Cell |
| **Tier 2** | IF 10-30 | Cancer Research, Blood, Cell Reports |
| **Tier 3** | IF 5-10 | BMC Cancer, PLOS ONE, Frontiers |
| **Tier 4** | IF < 5 | 기타 논문 |

### 6.4 필터링 기능

**지원하는 필터:**

| 필터 | 예시 | 용도 |
|------|------|------|
| `min_year` | 2020 | 최근 5년 논문만 |
| `max_year` | 2024 | 특정 기간 논문 |
| `min_citations` | 50 | 많이 인용된 논문 |
| `journal_tiers` | ["tier1"] | Nature급만 |
| `sources` | ["pmc"] | Peer-reviewed만 |
| `concepts` | ["immunotherapy"] | 특정 주제 |
| `authors` | ["Zhang F"] | 특정 저자 |

**사용 예시:**

```python
# "2020년 이후 Nature/Cell급 저널에서
#  50회 이상 인용된 면역항암제 논문만 검색"

results = search(
    query="PD-1 inhibitor efficacy",
    min_year=2020,
    min_citations=50,
    journal_tiers=["tier1", "tier2"],
    concepts=["immunotherapy"],
)
```

---

## 7. 품질 보장 시스템 (Quality Assurance - 3 Gates)

### 7.1 왜 3단계 검증인가요?

```
일반 AI 시스템:
질문 → AI 답변 → 출력
      (검증 없음)

OARIA:
질문 → [Gate 1] → 검색 → [Gate 2] → 답변 생성 → [Gate 3] → 출력
       도메인?      관련 논문?       답변 품질?
```

### 7.2 Gate 1: Domain Classifier

**목적**: 암 연구 질문만 허용

| 분류 | 행동 |
|------|------|
| oncology (암) | ✅ 통과 |
| cardiology (심장) | ❌ 거절 |
| neurology (신경) | ❌ 거절 |
| general_medicine | ❌ 거절 |
| non_medical | ❌ 거절 |

**신뢰도 임계값**: ≥ 80%

```
예시:
"EGFR 변이 치료법" → oncology 95% → ✅ 통과
"혈압약 추천" → cardiology 87% → ❌ 거절

거절 메시지:
"저는 암 연구 전문 AI입니다.
 심장 관련 질문은 해당 전문 리소스를 참고해 주세요."
```

### 7.3 Gate 2: Retrieval Confidence

**목적**: 충분한 증거 논문이 있는지 확인

**통과 조건:**
1. 최고 유사도 점수 ≥ 0.7
2. 관련 논문 ≥ 3개 (유사도 0.6 이상)
3. 암 관련 논문 비율 ≥ 80%

```
예시 1 (통과):
질문: "EGFR 변이 치료"
검색 결과: 15개 논문, 최고점수 0.89
→ ✅ 충분한 증거 있음

예시 2 (실패):
질문: "희귀암 XYZ의 치료법"
검색 결과: 1개 논문, 최고점수 0.52
→ ❌ 증거 부족

실패 메시지:
"해당 질문에 대한 충분한 근거를 찾지 못했습니다.
 질문을 더 구체화하거나 다른 키워드로 시도해 주세요."
```

### 7.4 Gate 3: RAGAS Evaluation

**목적**: 생성된 답변이 논문 내용에 충실한지 확인

**평가 지표:**

| 지표 | 측정 내용 | 목표 |
|------|-----------|------|
| **Faithfulness** | 답변이 논문에 있는 내용인가? | ≥ 0.85 |
| **Answer Relevancy** | 답변이 질문에 맞는가? | ≥ 0.80 |

```
Faithfulness 예시:

논문 내용: "Osimertinib showed 71% response rate"
AI 답변: "Osimertinib shows about 70% response rate"
→ Faithfulness 0.95 (충실함) ✅

AI 답변: "Osimertinib cures 90% of patients"
→ Faithfulness 0.30 (환각) ❌
```

**낮은 점수 시:**
> "⚠️ 이 답변의 신뢰도가 다소 낮습니다.
> 출처 논문을 직접 확인하시기 바랍니다."

---

## 8. 기술 스택 정당화 (Technology Justification)

### 8.1 기술 선택 요약

| 구성요소 | 선택 기술 | 대안 | 선택 이유 |
|----------|-----------|------|-----------|
| 논문 API | OpenAlex | PubMed | 더 많은 논문, 더 쉬운 API |
| 벡터 DB | Qdrant | Pinecone | 오픈소스, Hybrid 검색 지원 |
| 임베딩 | BGE-M3 | PubMedBERT | 최신 SOTA, Hybrid, 한국어 |
| 키워드 | BGE-M3 Sparse | BM25 | 별도 시스템 불필요 |
| LLM | Claude API | GPT-4 | Anthropic 협력 |
| 평가 | RAGAS | 수동 평가 | 자동화, 업계 표준 |

### 8.2 OpenAlex vs PubMed

```
PubMed 장점:
- 생명과학 전문
- 익숙함

OpenAlex 장점:
- PubMed 전체 포함 + 2억 논문 더
- API 사용 쉬움 (키 불필요)
- 인용수, 개념 등 풍부한 메타데이터
- 더 빠른 요청 속도

결론: OpenAlex가 PubMed를 포함하므로 손실 없이 더 많은 이점
```

### 8.3 BGE-M3 vs PubMedBERT

```
PubMedBERT:
- 2020년 모델 (오래됨)
- 의학 도메인 특화
- Dense 벡터만 생성
- 영어만 지원

BGE-M3:
- 2024년 최신 모델
- Dense + Sparse 동시 생성
- 100+ 언어 지원 (한국어!)
- 최신 벤치마크 1위

결론: 범용 모델인 BGE-M3가 도메인 특화 모델보다 실제 성능 더 우수
     (최신 연구에서 증명됨)
```

### 8.4 Hybrid Search vs Dense Only

```
Dense Only 문제:
질문: "T790M mutation"
Dense: "EGFR 변이" (의미 유사) 도 높은 점수
→ 정확한 T790M 찾기 어려울 수 있음

Hybrid 장점:
Dense: 의미 유사한 것 찾기
Sparse: 정확한 용어 일치
→ 둘의 장점 결합

의학/생명과학에서 중요:
- 유전자명 (EGFR, KRAS, BRAF) → 정확히 일치해야 함
- 약물명 (osimertinib) → 정확히 일치해야 함
- 일반 개념 → 의미 검색으로 확장
```

---

## 9. 성능 목표 (Performance Targets)

### 9.1 목표 지표

| 지표 | 목표값 | 현재 | 설명 |
|------|--------|------|------|
| 논문 수집 | ≥ 1,000 | 975 ✅ | Full-text 논문 |
| Precision@5 | ≥ 80% | 🔄 | 상위 5개 중 관련 비율 |
| Faithfulness | ≥ 0.85 | 🔄 | 답변의 논문 충실도 |
| Relevancy | ≥ 0.80 | 🔄 | 답변의 질문 적합도 |
| 응답 시간 | < 3초 | 🔄 | 단순 질문 기준 |
| 도메인 정확도 | ≥ 95% | 🔄 | 암 vs 비암 분류 |

### 9.2 측정 방법

**Precision@5 (검색 정확도):**
```
검색 결과 상위 5개 중 실제 관련 있는 비율

예: 5개 중 4개 관련 → 80%
```

**Faithfulness (충실도):**
```
RAGAS 프레임워크로 자동 측정
- 답변의 각 문장이 논문에 근거하는지 확인
- 환각(hallucination) 감지
```

### 9.3 테스트 쿼리 예시

```
1. 단순 질문:
   "EGFR 억제제의 종류는?"

2. 비교 질문:
   "1세대 vs 3세대 EGFR TKI 비교"

3. 복잡한 질문:
   "T790M 내성 발생 후 치료 전략과 최근 임상시험 결과"

4. 도메인 외 (거절해야 함):
   "고혈압 치료제 추천"
```

---

## 부록: 용어 설명

| 용어 | 설명 |
|------|------|
| **RAG** | Retrieval-Augmented Generation, 검색 기반 AI 답변 생성 |
| **Chunk** | 긴 텍스트를 작은 조각으로 나눈 것 |
| **Embedding** | 텍스트를 수학적 벡터(숫자 배열)로 변환 |
| **Vector DB** | 벡터를 저장하고 유사도로 검색하는 데이터베이스 |
| **Hybrid Search** | 의미 검색 + 키워드 검색 결합 |
| **RAGAS** | RAG 시스템 평가 프레임워크 |
| **Gate** | 품질 검증 단계 (통과/거절 결정) |
| **Tier** | 저널의 영향력에 따른 등급 |
| **Full-text** | 논문 초록이 아닌 전체 본문 |
| **Peer-reviewed** | 전문가 검토를 거친 정식 출판 논문 |

---

## 문서 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2025-12-31 | 최초 작성 |

---

*이 문서에 대한 질문이나 피드백은 김혜민에게 연락해 주세요.*
