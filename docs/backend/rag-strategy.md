# RAG 전략: 청킹 & 컨텍스트 설계

> **Last Updated**: 2026-01-01

---

## 1. 청킹 전략 비교

### 1.1 주요 청킹 방식

| 전략 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **고정 청킹** | N자/토큰씩 균일 분할 | 구현 단순 | 의미 단위 무시 |
| **Parent-Child** | 작은 청크로 검색, 큰 청크로 반환 | 검색 정밀도 높음 | 작은 청크가 무의미할 수 있음 |
| **Semantic** | 임베딩 유사도로 문장 그룹핑 | 의미 기반 분할 | 계산 비용 높음 |
| **섹션 기반 Recursive** | 문서 구조 유지 + 의미 단위 분할 | 맥락 유지 | 청크 크기 가변적 |

### 1.2 현재 구현: 섹션 기반 Recursive Chunking

```
논문
 ├─ Abstract     → 700토큰 이하면 1청크, 넘으면 문단/문장 단위 분할
 ├─ Introduction → 〃
 ├─ Methods      → 〃
 ├─ Results      → 〃
 └─ Discussion   → 〃
```

**분할 우선순위:**
```python
separators = ["\n\n", "\n", ". ", " "]
#             문단    줄바꿈  문장   공백
```

**설정값:**
- `chunk_size_tokens`: 700 (목표)
- `chunk_overlap_tokens`: 100 (embedding_input용)
- `min_chunk_tokens`: 50

**핵심 로직: 작은 섹션은 분할 X**
```python
# 섹션이 700 토큰 이하면 그대로 1청크로 유지
if self.count_tokens(text) <= self.chunk_size_tokens:
    return [chunk]  # 분할 없이 통째로!
```

| 섹션 | 보통 크기 | 처리 |
|------|----------|------|
| Abstract | ~300 토큰 | 통째로 1청크 |
| Introduction | ~800 토큰 | 분할 (2개) |
| Methods | ~1,500 토큰 | 분할 (2-3개) |
| Results | ~2,000+ 토큰 | 분할 (3-4개) |

→ 짧은 섹션의 의미가 잘리지 않도록 보존

---

## 2. 왜 섹션 기반인가? (도메인 특성)

### 2.1 암 논문의 특성

암 논문은 **구조화된 전문 문서**:
- 각 섹션이 완결된 의미 단위
- 약물명, 유전자 변이, 환자군 정보가 맥락과 함께 있어야 의미 있음
- 섹션 경계가 끊기면 해석 불가

### 2.2 Parent-Child의 한계 (이 도메인에서)

```
[200토큰 자식 청크]
"The overall response rate was 71% in patients receiving Osimertinib."
```

검색은 됨. 하지만:
- 어떤 환자군? (T790M? Exon 19 del?)
- 1차 치료? 2차 치료?
- 비교군 대비 결과는?

**작을수록 정밀 ≠ 작을수록 유의미**

### 2.3 섹션 기반의 장점

```
[700토큰 섹션 청크]
"Among 150 patients with EGFR T790M mutation who failed
first-line EGFR-TKI, Osimertinib showed 71% ORR (95% CI: 65-78%).
Median PFS was 10.1 months. Subgroup analysis revealed higher
response in patients without brain metastases (78% vs 62%)."
```

검색 자체가 이미 유의미한 맥락 포함.

---

## 3. LLM 컨텍스트 전달 전략

### 3.1 토큰 비용 현실

| 범위 | 크기 | Top-5 검색 시 |
|------|------|---------------|
| 청크 (현재) | ~700 토큰 | ~3,500 토큰 |
| 섹션 | ~1,500 토큰 | ~7,500 토큰 |
| 논문 전체 | ~8,000 토큰 | ~40,000 토큰 |

### 3.2 질문 유형별 전략

| 질문 유형 | 필요한 범위 | 예시 |
|-----------|-------------|------|
| **팩트 확인** | 섹션 | "Osimertinib 반응률은?" → Results만 |
| **방법론 질문** | 복수 섹션 | "환자군 선정 기준은?" → Methods + Results |
| **종합 판단** | 논문 전체 | "이 약 써도 될까?" → 전체 맥락 필요 |

### 3.3 추천: 단계적 확장 전략

```
1단계: 검색된 청크의 섹션 전체
       └─ Results 섹션 (1,500 토큰)

2단계: 관련 섹션 추가 (필요시)
       └─ Methods + Results (3,000 토큰)

3단계: 논문 전체 (정말 필요할 때만)
       └─ Abstract ~ Conclusion (8,000 토큰)
```

### 3.4 논문 수에 따른 분기

```python
if len(unique_papers) == 1:
    # 논문 1개 → fulltext 전체 OK
    context = fulltext

elif len(unique_papers) <= 3:
    # 논문 2-3개 → 각 논문의 검색된 섹션들
    context = [get_section(chunk) for chunk in results]

else:
    # 논문 많음 → 청크 + 약간 확장
    context = [expand_chunk(chunk, chars=500) for chunk in results]
```

---

## 4. 현재 구현에서 활용 가능한 필드

### 4.1 Chunk 구조

```python
@dataclass
class Chunk:
    chunk_id: str           # "pmc:PMC123|results|3"
    paper_id: str
    section: str

    text: str               # 원문 (700토큰)
    offset_start: int       # fulltext 내 시작 위치
    offset_end: int         # fulltext 내 끝 위치

    section_offset_start: int   # 섹션 시작 위치
    section_offset_end: int     # 섹션 끝 위치
    parent_expand_chars: int = 500
```

### 4.2 확장 예시

```python
# 검색 결과에서 섹션 전체 가져오기
section_text = fulltext[chunk.section_offset_start:chunk.section_offset_end]

# 청크 주변 확장
expanded = fulltext[chunk.offset_start - 500 : chunk.offset_end + 500]
```

---

## 5. 정리

| 구분 | 전략 |
|------|------|
| **검색** | 섹션 기반 청킹 (700토큰), 의미 단위 유지 |
| **반환 (단일 논문)** | 논문 전체 fulltext |
| **반환 (복수 논문)** | 각 논문의 해당 섹션 |
| **반환 (다수 논문)** | 청크 + 확장 (±500자) |

### 5.1 도메인별 권장

| 도메인 | 청킹 | 반환 |
|--------|------|------|
| 일반 문서, FAQ | Parent-Child (작은 청크) | 부모 청크 |
| **논문, 법률, 의료** | 섹션 기반 (큰 청크) | 섹션 또는 문서 전체 |

---

## 6. TODO / 개선 아이디어

- [ ] 질문 유형 자동 분류 → 컨텍스트 범위 동적 결정
- [ ] Abstract 항상 포함 옵션 (논문 요약 제공)
- [ ] 관련 섹션 자동 추가 (Results 검색 시 Methods도 함께)
- [ ] 토큰 예산 기반 동적 확장
