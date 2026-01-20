# OAR-29 Chunker 트러블슈팅

> 청킹 구현 중 발견된 문제들과 해결 방안 정리

---

## 1. 섹션 파싱: DB 조회 필수

### 문제 상황

fulltext 파일에서 `[SECTION]` 패턴으로 섹션을 파싱하면 **잘못된 섹션이 인식**됨.

```
# fulltext 파일 직접 파싱 결과 (잘못됨)
📑 발견된 섹션: 13개
  [ 1] title
  [ 2] abstract
  [ 3] introduction
  ...
  [ 7] t3                    ← ??? 이상한 섹션
  [ 8] t4                    ← ???
  [11] ica512                ← ???
  [12] ptprn                 ← ???
```

### 원인

논문 본문에 **약어 표기**가 `[대문자]` 형태로 존재:

```
원본 논문 텍스트:
"...thyroid hormones (triiodothyronine [T3] and thyroxine [T4])..."
                                        ↑          ↑
                                    약어 표기 (섹션 아님!)
```

`[T3]`, `[T4]`, `[ICA512]`, `[PTPRN]` 등은 의학 용어의 약어이지 섹션 마커가 아님.

### 해결: PostgreSQL에서 섹션 정보 조회

XML 파서(`xml_parser.py`)가 원본 XML의 `<sec>` 태그를 정확히 파싱하여 DB에 저장함.

```sql
-- paper_sections 테이블 (정확한 8개 섹션)
SELECT section_order, section_name FROM paper_sections WHERE paper_id = '...';

 section_order |                    section_name
---------------+----------------------------------------------------
             1 | abstract
             2 | introduction
             3 | direct local neural input regulation
             4 | cns neurotransmitter-mediated peripheral immune regulation
             5 | hormone-mediated systemic immune modulation
             6 | regulation of neural signaling by the immune system and tumors
             7 | emerging cancer therapies targeting the neuro-immune axis
             8 | discussion
```

### 결론

| 방식 | 결과 |
|------|------|
| fulltext 패턴 파싱 | ❌ 13개 섹션 (오인식 포함) |
| **PostgreSQL 조회** | ✅ **8개 섹션 (정확)** |

**반드시 DB에서 섹션 정보를 가져와야 함!**

```python
# 올바른 데이터 흐름
paper_sections = fetch_from_postgresql(paper_id)  # 섹션 정보
fulltext = fetch_from_minio(canonical_prefix)      # 원문 텍스트
result = chunker.chunk_paper(fulltext, paper_sections)  # 청킹
```

---

## 2. Offset 검증 실패: 오버랩 버그

### 문제 상황

청킹 후 offset 검증 시 대부분 실패:

```
PMC12570465: 8/44 통과  (36개 실패)
PMC12583504: 15/28 통과 (13개 실패)
PMC12625643: 3/23 통과  (20개 실패)
```

검증 실패 예시:
```
❌ introduction|1
   offset: 4553 ~ 6337
   stored:    '(5-HT), and glutamic acid (Glu) have traditionally...'
   extracted: 'xytryptamine (5-HT), and glutamic acid (Glu) have...'
```

stored와 extracted 텍스트가 다름!

### 원인 분석

#### 1단계: 텍스트 분할 (정상)

```python
# _recursive_split() 결과
chunk[0] = "...dopamine (DA), gamma-aminobutyric acid (GABA), 5-hydroxytryptamine"
chunk[1] = "(5-HT), and glutamic acid..."  # 원래 시작 위치
```

#### 2단계: 오버랩 적용 (문제 발생!)

```python
# _apply_overlap() - 이전 청크 끝부분을 현재 청크 앞에 붙임
def _apply_overlap(self, chunks):
    overlap_text = prev_chunk[-400:]  # 이전 청크 끝 400자
    result.append(overlap_text + curr_chunk)  # ← 텍스트 변형!
```

```
chunk[1] = "aminobutyric acid (GABA), 5-hydroxytryptamine (5-HT), and glutamic acid..."
           ↑ 오버랩이 앞에 붙어서 텍스트가 변형됨!
```

#### 3단계: Offset 계산 (엉뚱한 결과)

```python
# _chunk_section()
pos = text.find(chunk_text, current_offset)  # 변형된 텍스트를 원본에서 찾음
if pos == -1:
    pos = text.find(chunk_text)  # 못 찾아서 처음부터 다시 찾음 → 엉뚱한 위치!
```

### 버그 흐름 정리

```
원본 fulltext:
"...5-hydroxytryptamine (5-HT), and glutamic acid (Glu) have traditionally..."
                        ↑
                    실제 chunk[1] 시작 위치

1. _recursive_split 후: chunk[1] = "(5-HT), and glutamic acid..."
2. _apply_overlap 후:   chunk[1] = "tryptamine (5-HT), and glutamic acid..."  (변형!)
3. text.find() 실행:    변형된 텍스트는 원본에서 못 찾음 → pos = -1
4. 결과:                엉뚱한 offset 저장
```

### 해결 방안

**오버랩 적용 전에 offset을 먼저 계산, chunk.text는 원본 유지**

```python
# 수정된 흐름
def _chunk_section(self, ...):
    # 1. 오버랩 없이 순수 분할
    split_texts = self._recursive_split_no_overlap(text)

    # 2. 원본 텍스트로 정확한 offset 계산
    for chunk_text in split_texts:
        pos = text.find(chunk_text)  # 원본이라 정확히 찾음!
        chunk = Chunk(
            text=chunk_text,           # 원본 텍스트 저장
            offset_start=section.offset_start + pos,
            offset_end=section.offset_start + pos + len(chunk_text),
        )

    # 3. 오버랩은 embedding_input에만 적용 (검색 품질용)
    for chunk in chunks:
        overlap_start = max(section.offset_start, chunk.offset_start - 400)
        overlap_text = fulltext[overlap_start:chunk.offset_end]
        chunk.embedding_input = f"[TITLE]...\n[TEXT]{overlap_text}"
```

### 수정 결과 ✅

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| `chunk.text` | 오버랩 포함 (변형) | **원본 그대로** |
| `offset_start/end` | 엉뚱한 값 | **정확한 값** |
| Offset 검증 | 8/44 통과 | **43/43 통과 (100%)** |
| 근거 재현 | ❌ 불가 | ✅ **100% 재현** |
| `embedding_input` | 오버랩 미포함 | 오버랩 포함 (검색용) |

**실제 테스트 결과:**
```
PMC12570465: 43/43 통과 (100%)
PMC12583504: 28/28 통과 (100%)
PMC12625643: 23/23 통과 (100%)
```

---

## 요약

| 문제 | 원인 | 해결 | 상태 |
|------|------|------|------|
| 섹션 오인식 | fulltext의 `[T3]`, `[T4]` 약어 | **PostgreSQL에서 섹션 조회** | ✅ |
| Offset 검증 실패 | 오버랩 적용 후 텍스트 변형 | **원본 텍스트로 offset 계산, 오버랩은 embedding_input에만** | ✅ |

---

## 데모 실행 방법

```bash
# 권장: DB + S3에서 실제 데이터 사용
uv run python src/demo.py

# 샘플 데이터 (테스트용)
uv run python src/demo.py --sample

# 로컬 파일 (섹션 오인식 주의!)
uv run python src/demo.py --file docs/PMC12570465.txt
```
