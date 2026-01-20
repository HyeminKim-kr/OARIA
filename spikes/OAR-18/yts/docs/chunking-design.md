# OAR-18: 암 논문 청킹 설계

> **목적**: Europe PMC에서 수집한 암 논문을 RAG용으로 청킹하는 전략 설계
>
> **작성일**: 2025-12-23
>
> **상태**: 설계 확정 (v2 - 피드백 반영)

---

## TL;DR (핵심 결정)

| 항목 | 결정 | 이유 |
|------|------|------|
| **청킹 전략** | Section + Recursive | offset 재현 보장, 논문 구조 활용 |
| **청크 크기** | 600-800 토큰 | 논문 질의는 컨텍스트 넓음, parent 확장으로 보완 |
| **오버랩** | 10-15% (80-120 토큰) | 문맥 유지 |
| **Parent-Child** | child만 저장, parent_span 메타 | 저장량 최소화, S3에서 확장 |
| **임베딩 입력** | `[TITLE][SECTION][TEXT]` prefix | Contextual Retrieval 효과, offset 무관 |
| **배제 전략** | Agentic, Proposition, Neural | LLM 재작성 → offset 1:1 매핑 깨짐 |

---

## 시스템 제약 조건 ⚠️

### offset 기반 근거 재현이 최우선

우리 시스템은 Weaviate에 청크 저장 시 `offsetStart/End + textVersion`을 함께 저장하여 **근거 재현/하이라이트**를 지원한다 (OAR-20 Weaviate 스키마 참조).

```
┌─────────────────────────────────────────────────────────────┐
│  핵심 제약: 청크 → canonical text 역추적 가능해야 함           │
├─────────────────────────────────────────────────────────────┤
│  필수 산출물:                                                 │
│  - content (청크 텍스트)                                      │
│  - offsetStart, offsetEnd (canonical text 기준 char index)  │
│  - textVersion (canonical 버전)                              │
│                                                              │
│  → textVersion이 바뀌면 청크 재생성 필요                       │
└─────────────────────────────────────────────────────────────┘
```

### 배제되는 전략들

| 전략 | 배제 이유 |
|------|----------|
| **Agentic Chunking** | LLM이 텍스트 재구성 → offset 1:1 매핑 불가 |
| **Proposition-Based** | 원문 → 명제 변환 → 원문 위치 추적 불가 |
| **Neural Chunking** | 모델이 경계 결정 → 재현성 불안정 |

> 이 전략들은 검색 성능은 좋아지지만, **원문 기반 근거 재현**이 어려워짐.

---

## 데이터 특성 분석

### Europe PMC 전문 데이터

| 항목 | 값 | 비고 |
|------|-----|------|
| 평균 전문 길이 | ~30,000자 | 약 7,500-10,000 토큰 |
| 섹션 구조 | 6개 | Abstract, Introduction, Methods, Results, Discussion, Conclusion |
| 포맷 | XML → Plain Text | HTML 엔티티 잔존 (`&#x02010;` 등) |

### 샘플 데이터 (PMC12707179)

```
전문 길이: 32,200자
섹션별 길이 (추정):
- Abstract:     ~2,000자
- Introduction: ~3,000자
- Methods:      ~5,000자
- Results:      ~8,000자 (가장 김)
- Discussion:   ~6,000자
- Conclusion:   ~1,500자
- 기타 (참조 등): ~6,000자
```

---

## 전처리 파이프라인

### 1단계: XML → Clean Text

```
원본 XML
    ↓
HTML 엔티티 디코딩 (&#x02010; → -)
    ↓
태그 제거 (현재 정규식 기반)
    ↓
공백 정규화
    ↓
참조 정리 (1, 2, 3 → [1-3] 또는 제거)
    ↓
Clean Text
```

### 개선 필요 사항

| 현재 | 문제 | 개선 |
|------|------|------|
| 정규식으로 태그 제거 | 섹션 구분 손실 | XML 파서 (lxml) 사용 |
| 단순 문자열 find | 섹션 위치 부정확 | XML 태그 기반 섹션 추출 |
| HTML 엔티티 잔존 | 텍스트 품질 저하 | `html.unescape()` 적용 |

---

## 청킹 전략

### 권장: 섹션 기반 Recursive Chunking

논문의 구조적 특성을 활용한 2단계 청킹:

```
┌──────────────────────────────────────────────────────┐
│  1단계: 섹션 분리                                      │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐ │
│  │Abstract │Intro    │Methods  │Results  │Discussion│ │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘ │
└──────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────┐
│  2단계: 섹션 내 Recursive Split                        │
│  Results 섹션 예시:                                    │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐   │
│  │ R_0 │ R_1 │ R_2 │ R_3 │ R_4 │ R_5 │ R_6 │ R_7 │   │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘   │
│         ↑ 오버랩 ↑                                    │
└──────────────────────────────────────────────────────┘
```

### 청킹 파라미터 (확정)

| 파라미터 | 값 | 근거 |
|---------|-----|------|
| **청크 크기** | 600-800 토큰 (~2000-2600자) | 논문 질의는 "조건+결과+endpoint" 한 덩어리, parent 확장으로 보완 |
| **오버랩** | 10-15% (80-120 토큰) | 문맥 유지, 의미 절단 방지 |
| **분할 우선순위** | `["\n\n", "\n", ". ", " "]` | 문단 → 줄 → 문장 → 단어 |
| **최소 청크 크기** | 100 토큰 | 너무 짧은 청크 방지 |
| **섹션 경계** | 최소 경계로 강제 | 섹션 넘어서 청크 생성 금지 |

> **왜 512보다 크게?**: 논문 질문은 종종 여러 요소가 한 덩어리에 걸침. 검색은 child로 하되, LLM 컨텍스트는 parent 확장으로 보완.

### 섹션별 처리

| 섹션 | 특성 | 처리 |
|------|------|------|
| **Abstract** | 짧음, 요약 정보 | 1-2 청크, 그대로 유지 |
| **Introduction** | 배경 지식 | 일반 청킹 |
| **Methods** | 실험 방법, 세부 정보 | 일반 청킹 |
| **Results** | 핵심 데이터, 수치 | 더 작은 청크 (600-800자) |
| **Discussion** | 해석, 비교 | 일반 청킹 |
| **Conclusion** | 짧음, 결론 | 1-2 청크, 그대로 유지 |

---

## Parent-Child 전략: 저장 없이 구현 ⭐

### 왜 Parent-Child인가?

논문 RAG에서 Parent-Child의 장점:
- **검색은 작게** (child): 정밀한 semantic matching
- **생성은 크게** (parent): LLM에 충분한 컨텍스트 제공

### 가성비 구현 (권장)

**Parent 청크를 별도 저장하지 않는다**. 대신:

```
┌─────────────────────────────────────────────────────────────┐
│  Weaviate 저장 (child만)                                     │
├─────────────────────────────────────────────────────────────┤
│  - chunk_id, text, section, offset_start, offset_end        │
│  - parent_expand_chars: 500  ← 확장 규칙만 저장              │
│  - text_version                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    검색 hit 발생 시
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  S3 canonical에서 parent 범위 확장                           │
├─────────────────────────────────────────────────────────────┤
│  parent_start = max(0, offset_start - parent_expand_chars)  │
│  parent_end = min(len, offset_end + parent_expand_chars)    │
│  → 같은 섹션 내에서만 확장 (섹션 경계 존중)                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    LLM에 parent 컨텍스트 제공
```

### 장점

| 항목 | 효과 |
|------|------|
| **저장량** | child 수준 유지 (parent 별도 저장 X) |
| **검색 정밀도** | 작은 child로 semantic matching |
| **LLM 컨텍스트** | 런타임에 parent 확장 |
| **유연성** | expand_chars 값 조정 가능 |

---

## Contextual Embedding: LLM 없이 효과 얻기 ⭐

### 핵심 아이디어

Anthropic의 Contextual Retrieval에서 "청크에 컨텍스트 추가"가 핵심이지만, **LLM 요약 없이도** 메타데이터 prefix만으로 효과를 볼 수 있다.

### 임베딩 입력 포맷

```python
# 원문 텍스트 (저장용) - offset 재현에 사용
original_text = "In total, 198 RMB cases with oncocytic features..."

# 임베딩 입력 (검색용) - prefix 추가
embedding_input = """[TITLE] Immunotherapy Response in Lung Cancer
[SECTION] Results
[YEAR] 2023
[TEXT] In total, 198 RMB cases with oncocytic features..."""
```

### 왜 이게 작동하는가?

| 요소 | 효과 |
|------|------|
| **Title** | 논문 주제와 질의 매칭 향상 |
| **Section** | "치료 결과" 질의 → Results 섹션 우선 |
| **Year** | 최신 연구 선호 시 가중치 |

### offset 재현과 충돌 없음

```
임베딩 입력: [TITLE]...[SECTION]...[TEXT] chunk_text
                                    ↑
                              이 부분만 offset으로 추적

저장되는 text 필드: chunk_text (원문 그대로)
offset_start/end: canonical text 기준 (prefix 제외)
```

> 원문은 S3 canonical에 그대로 있고, prefix는 **임베딩 생성 시에만** 사용.

---

## 청크 스키마 (Weaviate)

### chunk_id 규칙

```
{paper_id}|{section}|{index}

예시:
- pmid:12345678|abstract|0
- pmid:12345678|results|3
- pmid:12345678|methods|2
```

### 청크 메타데이터 (확정)

```json
{
  "chunk_id": "pmid:12345678|results|3",
  "paper_id": "pmid:12345678",
  "section": "results",
  "chunk_index": 3,
  "offset_start": 12340,
  "offset_end": 13280,
  "char_count": 940,
  "text": "In total, 198 RMB cases with oncocytic features were identified...",
  "text_version": "v1",
  "parent_expand_chars": 500,
  "section_offset_start": 10000,
  "section_offset_end": 18000
}
```

### PostgreSQL papers 테이블 연계

```sql
-- 청크 조회 시 papers와 JOIN
SELECT
    c.chunk_id,
    c.text,
    c.section,
    p.title,
    p.canonical_bucket,
    p.canonical_prefix
FROM weaviate_chunks c  -- (가상, 실제는 Weaviate 쿼리)
JOIN papers p ON p.paper_id = c.paper_id
WHERE c.chunk_id = 'pmid:12345678|results|3';
```

---

## 검색 전략: 하이브리드 (메타데이터 필터링) ⭐ 권장

### 왜 메타데이터 필터링인가?

| 방식 | 설명 | 장단점 |
|------|------|--------|
| **메타데이터 필터링** | 메타데이터를 구조화 필드로 저장, WHERE 조건으로 검색 | ✅ 빠름, 정확한 필터 |
| 메타데이터 임베딩 | 메타데이터를 텍스트에 포함하여 함께 임베딩 | ❌ 비용↑, 유연성↓ |

**암 논문 검색에서는 메타데이터 필터링이 적합**:
- `section` 필터: "Results 섹션에서만 검색" → 핵심 데이터 집중
- `year` 필터: "2020년 이후 논문만" → 최신 연구 우선
- `paper_id` 필터: "특정 논문 내 검색" → 근거 추적

### 검색 흐름

```
유저 질의: "EGFR mutation treatment efficacy"
필터: year >= 2020, section = results
                    ↓
┌───────────────────┴───────────────────┐
↓                                       ↓
[메타데이터 필터]                    [벡터 검색]
 - year >= 2020                      의미적 유사도 계산
 - section = "results"               (임베딩 비교)
↓                                       ↓
후보군 축소 (Pre-filtering)          Top-K 결과
└───────────────────┬───────────────────┘
                    ↓
            최종 검색 결과 (교집합)
```

### Weaviate 쿼리 예시

```python
import weaviate

client = weaviate.Client("http://localhost:8080")

# 하이브리드 검색: 벡터 + 메타데이터 필터
result = (
    client.query
    .get("PaperChunk", ["text", "section", "paper_id", "chunk_id"])
    .with_near_text({
        "concepts": ["EGFR mutation treatment efficacy"]
    })
    .with_where({
        "operator": "And",
        "operands": [
            {
                "path": ["year"],
                "operator": "GreaterThanEqual",
                "valueInt": 2020
            },
            {
                "path": ["section"],
                "operator": "Equal",
                "valueText": "results"
            }
        ]
    })
    .with_limit(10)
    .do()
)
```

### 필터링 가능 메타데이터

| 필드 | 타입 | 용도 | 예시 |
|------|------|------|------|
| `section` | text | 섹션 필터 | `= "results"` |
| `year` | int | 출판년도 필터 | `>= 2020` |
| `paper_id` | text | 특정 논문 내 검색 | `= "pmid:12345678"` |
| `journal` | text | 저널 필터 | `= "Nature"` |
| `chunk_index` | int | 청크 순서 | 범위 검색 |

### 고급: BM25 + 벡터 하이브리드 (향후)

Weaviate는 BM25 키워드 검색도 지원:

```python
# 키워드 + 벡터 하이브리드
.with_hybrid({
    "query": "EGFR mutation",
    "alpha": 0.5  # 0=BM25, 1=벡터, 0.5=균형
})
```

> 💡 **Anthropic Contextual Retrieval**: BM25 + 벡터 + 리랭킹 조합으로 검색 에러 67% 감소

---

## 예상 수치

### 논문 1편당

| 항목 | 예상값 |
|------|--------|
| 총 청크 수 | 20-35개 |
| Abstract | 1-2개 |
| Introduction | 3-5개 |
| Methods | 4-7개 |
| Results | 6-10개 |
| Discussion | 4-8개 |
| Conclusion | 1-2개 |

### 전체 규모

| 논문 수 | 청크 수 | 저장 용량 (추정) |
|---------|---------|-----------------|
| 1,000편 | ~25,000개 | ~25MB (텍스트) |
| 10,000편 | ~250,000개 | ~250MB |
| 100,000편 | ~2,500,000개 | ~2.5GB |

---

## 구현 계획 (러프)

### Phase 1: 기본 청킹 (확정 버전)

```python
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 토큰 카운터 (OpenAI 기준)
enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

def chunk_paper(
    paper_id: str,
    title: str,
    year: int,
    sections: dict[str, tuple[str, int, int]],  # {section: (text, offset_start, offset_end)}
    chunk_size_tokens: int = 700,
    overlap_tokens: int = 100,
    parent_expand_chars: int = 500
) -> list[dict]:
    """
    섹션별 청킹 with offset 추적 + contextual prefix
    """
    # 토큰 → 문자 변환 (대략 1토큰 = 3.5자)
    chunk_size_chars = int(chunk_size_tokens * 3.5)
    overlap_chars = int(overlap_tokens * 3.5)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " "],
        length_function=lambda x: count_tokens(x)  # 토큰 기준
    )

    chunks = []
    for section_name, (section_text, sec_start, sec_end) in sections.items():
        if section_name == "full":
            continue

        section_chunks = splitter.split_text(section_text)
        current_offset = sec_start

        for i, chunk_text in enumerate(section_chunks):
            # 청크의 실제 offset 계산
            chunk_start_in_section = section_text.find(chunk_text)
            offset_start = sec_start + chunk_start_in_section
            offset_end = offset_start + len(chunk_text)

            chunks.append({
                "chunk_id": f"{paper_id}|{section_name}|{i}",
                "paper_id": paper_id,
                "section": section_name,
                "chunk_index": i,
                "text": chunk_text,  # 원문 그대로 저장
                "offset_start": offset_start,
                "offset_end": offset_end,
                "section_offset_start": sec_start,
                "section_offset_end": sec_end,
                "parent_expand_chars": parent_expand_chars,
                "text_version": "v1",
                # 임베딩용 prefix (저장 X, 임베딩 시에만 사용)
                "_embedding_input": f"[TITLE] {title}\n[SECTION] {section_name}\n[YEAR] {year}\n[TEXT] {chunk_text}"
            })

    return chunks
```

### 임베딩 생성 시

```python
def get_embedding(chunk: dict, embed_model) -> list[float]:
    """임베딩 생성 - contextual prefix 포함"""
    # _embedding_input 사용 (prefix 포함)
    text_for_embedding = chunk["_embedding_input"]
    return embed_model.encode(text_for_embedding)

def store_to_weaviate(chunk: dict, embedding: list[float]):
    """Weaviate 저장 - 원문만 저장, prefix 제외"""
    weaviate_obj = {
        "chunk_id": chunk["chunk_id"],
        "paper_id": chunk["paper_id"],
        "section": chunk["section"],
        "text": chunk["text"],  # 원문만!
        "offset_start": chunk["offset_start"],
        "offset_end": chunk["offset_end"],
        # ... 기타 메타데이터
    }
    # embedding은 별도 벡터로 저장
```

### Phase 2: 전처리 개선

- XML 파서로 섹션 추출 고도화
- offset 계산 정확도 향상
- HTML 엔티티 완전 제거

### Phase 3: 임베딩 + Weaviate 저장

```python
# Weaviate 스키마 (OAR-20 참조)
{
    "class": "PaperChunk",
    "properties": [
        {"name": "chunk_id", "dataType": ["text"]},
        {"name": "paper_id", "dataType": ["text"]},
        {"name": "section", "dataType": ["text"]},
        {"name": "chunk_index", "dataType": ["int"]},
        {"name": "text", "dataType": ["text"]},
        {"name": "offset_start", "dataType": ["int"]},
        {"name": "offset_end", "dataType": ["int"]},
        {"name": "text_version", "dataType": ["text"]}
    ],
    "vectorizer": "text2vec-openai"  # 또는 커스텀
}
```

---

## 결정 사항 요약 (확정)

| 항목 | 결정 | 근거 |
|------|------|------|
| **청킹 전략** | Section + Recursive | offset 재현 보장 |
| **청크 크기** | 600-800 토큰 | 논문 컨텍스트 + parent 확장 |
| **오버랩** | 10-15% (80-120 토큰) | 문맥 유지 |
| **전처리** | XML 파서 (lxml) | 섹션 offset 정확도 |
| **검색 전략** | 메타데이터 필터링 ⭐ | section/year 필터 활용 |
| **Parent-Child** | child만 저장, 런타임 확장 | 저장량 최소화 |
| **임베딩 입력** | `[TITLE][SECTION][TEXT]` prefix | Contextual Retrieval |
| **임베딩 모델** | MedCPT vs OpenAI 크로스체크 | 의료 도메인 vs 일반 비교 필요 |
| **배제 전략** | Agentic, Proposition, Neural | offset 1:1 매핑 깨짐 |

---

## 평가 지표 ⭐

### 기본 검색 품질

| 지표 | 설명 | 목표 |
|------|------|------|
| **Recall@10** | 상위 10개 중 관련 청크 비율 | > 80% |
| **Precision@10** | 상위 10개 중 정확히 맞는 비율 | > 60% |
| **MRR** | 첫 번째 관련 결과 순위 역수 | > 0.7 |
| **nDCG@10** | 순위 품질 (가중치 적용) | > 0.7 |

### 근거 재현 품질 (우리 서비스 핵심)

| 지표 | 설명 | 측정 방법 |
|------|------|----------|
| **Evidence Reproducibility Rate** | offset으로 다시 뽑았을 때 snippet 일치율 | `재현된 snippet == 저장된 text` 비율 |
| **Section Hit Rate** | 질의 유형별 "맞는 섹션"에서 근거 나오는 비율 | 치료 질의 → Results, 방법 질의 → Methods |

### 평가 쿼리셋 (암/종양학)

```python
evaluation_queries = [
    # 치료 효과 (Results 기대)
    {"query": "EGFR mutation treatment response rate", "expected_section": "results"},
    {"query": "Immunotherapy efficacy in melanoma", "expected_section": "results"},

    # 방법론 (Methods 기대)
    {"query": "How was the clinical trial designed", "expected_section": "methods"},
    {"query": "Patient inclusion criteria", "expected_section": "methods"},

    # 배경 (Introduction 기대)
    {"query": "Current understanding of BRCA mutations", "expected_section": "introduction"},

    # 해석 (Discussion 기대)
    {"query": "Limitations of the study", "expected_section": "discussion"},
]
```

---

## 다음 단계

### Phase 1: 기본 구현
- [ ] XML 파서 기반 섹션 추출 (lxml)
- [ ] 섹션별 offset 계산 로직
- [ ] Recursive chunking with 섹션 경계 존중

### Phase 2: 임베딩 파이프라인
- [ ] Contextual embedding prefix 구현 (`[TITLE][SECTION][TEXT]`)
- [ ] 임베딩 모델 선정 (MedCPT vs OpenAI 크로스체크)
- [ ] Weaviate 저장 + parent_expand_chars 메타

### Phase 3: 검색 + Parent 확장
- [ ] 검색 시 S3에서 parent 범위 확장 로직
- [ ] 섹션 경계 존중하는 확장 규칙

### Phase 4: 평가
- [ ] 평가 쿼리셋 구축 (20-30개)
- [ ] Evidence Reproducibility Rate 측정
- [ ] Section Hit Rate 측정
- [ ] 청크 크기/오버랩 A/B 테스트

---

## 참고

- [OAR-20 Weaviate 스키마 설계](../../OAR-20/yts/docs/weaviate-스키마-설계.md)
- [OAR-20 PostgreSQL 스키마 설계](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.3.md)
- [청킹 전략 리서치](./chunking-strategies-research.md)
