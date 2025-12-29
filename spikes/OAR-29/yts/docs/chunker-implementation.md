# OAR-29: 텍스트 Chunker 구현 설계

> **담당**: yts
>
> **작성일**: 2025-12-29
>
> **상태**: 설계 중

---

## TL;DR (핵심 결정)

| 항목 | 결정 | 근거 |
|------|------|------|
| **청킹 전략** | Section + Recursive | offset 재현 보장, 논문 구조 활용 |
| **청크 크기** | 600-800 토큰 (~2000-2600자) | 논문 질의는 컨텍스트 넓음 |
| **오버랩** | 10-15% (80-120 토큰) | 문맥 유지, 의미 절단 방지 |
| **Parent-Child** | child만 저장, S3 런타임 확장 | 저장량 최소화 |
| **임베딩 입력** | `[TITLE][SECTION][TEXT]` prefix | Contextual Retrieval 효과 |
| **offset 기준** | char index (UTF-8 decoded str) | Python 슬라이싱 호환 |

> **참고**: 태스크 제목의 "512 토큰, 50 오버랩"은 초기 설정이며,
> OAR-18 설계 검토 결과 **600-800 토큰, 10-15% 오버랩**으로 확정됨

---

## 시스템 제약 조건

### 1. offset 기반 근거 재현 (최우선)

```
┌─────────────────────────────────────────────────────────────┐
│  핵심 제약: 청크 → canonical text 역추적 가능해야 함           │
├─────────────────────────────────────────────────────────────┤
│  필수 산출물:                                                 │
│  - content (청크 텍스트)                                      │
│  - offset_start, offset_end (canonical text 기준 char index) │
│  - text_version (canonical 버전)                              │
│                                                              │
│  → textVersion이 바뀌면 청크 재생성 필요                       │
└─────────────────────────────────────────────────────────────┘
```

### 2. 데이터 저장소 연계

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Weaviate   │       │ PostgreSQL  │       │     S3      │
│ (Vector DB) │       │   (RDB)     │       │  (Storage)  │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ PaperChunk  │       │ papers      │       │ canonical/  │
│ - 청크+벡터 │  ───▶ │ - 메타데이터│  ───▶ │ {id}/v1.txt │
│ - offset    │       │ - prefix    │       │ (순수 텍스트)│
└─────────────┘       └─────────────┘       └─────────────┘
```

### 3. 배제되는 전략들

| 전략 | 배제 이유 |
|------|----------|
| **Agentic Chunking** | LLM이 텍스트 재구성 → offset 1:1 매핑 불가 |
| **Proposition-Based** | 원문 → 명제 변환 → 원문 위치 추적 불가 |
| **Neural Chunking** | 모델이 경계 결정 → 재현성 불안정 |

---

## 데이터 특성

### Europe PMC 전문 데이터

| 항목 | 값 | 비고 |
|------|-----|------|
| 평균 전문 길이 | ~30,000자 | 약 7,500-10,000 토큰 |
| 섹션 구조 | 6개 | Abstract, Introduction, Methods, Results, Discussion, Conclusion |
| 포맷 | XML → Plain Text | HTML 엔티티 잔존 가능 |

### 예상 청크 수 (논문 1편당)

| 섹션 | 예상 청크 수 |
|------|-------------|
| Abstract | 1-2개 |
| Introduction | 3-5개 |
| Methods | 4-7개 |
| Results | 6-10개 |
| Discussion | 4-8개 |
| Conclusion | 1-2개 |
| **합계** | **20-35개** |

---

## 청킹 파이프라인

### 전체 흐름

```
원본 XML (Europe PMC)
        ↓
┌─────────────────────────────────────┐
│ 1단계: 전처리 (XML → Clean Text)     │
│ - HTML 엔티티 디코딩                  │
│ - 섹션별 텍스트 추출 (lxml)           │
│ - 공백 정규화                         │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 2단계: Canonical Text 생성           │
│ - S3에 저장: canonical/{id}/v1.txt  │
│ - 순수 텍스트만 (헤더 없음)           │
│ - SHA256 해시 계산                   │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 3단계: 섹션 기반 Recursive Chunking  │
│ - 섹션별 offset 범위 기록             │
│ - 섹션 경계 존중 (넘어서 분할 금지)    │
│ - 오버랩 적용                         │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 4단계: 청크 메타데이터 생성           │
│ - chunk_id 생성                      │
│ - offset_start, offset_end 계산      │
│ - _embedding_input (prefix 포함)     │
└─────────────────────────────────────┘
        ↓
Weaviate 저장 (임베딩과 함께)
```

### 1단계: 전처리

```python
import html
from lxml import etree

def preprocess_xml(xml_content: str) -> dict[str, tuple[str, int, int]]:
    """
    XML → 섹션별 (텍스트, offset_start, offset_end) 추출

    Returns:
        {
            "abstract": ("Background: ...", 0, 1250),
            "introduction": ("Cancer is...", 1251, 4500),
            ...
        }
    """
    # HTML 엔티티 디코딩
    decoded = html.unescape(xml_content)

    # lxml로 섹션 추출
    tree = etree.fromstring(decoded.encode())

    sections = {}
    current_offset = 0

    for section_name in ["abstract", "introduction", "methods",
                         "results", "discussion", "conclusion"]:
        text = extract_section(tree, section_name)
        if text:
            text = normalize_whitespace(text)
            offset_start = current_offset
            offset_end = current_offset + len(text)
            sections[section_name] = (text, offset_start, offset_end)
            current_offset = offset_end + 1  # +1 for section separator

    return sections
```

### 2단계: Canonical Text 생성

```python
import hashlib

def create_canonical_text(sections: dict) -> tuple[str, str]:
    """
    섹션들을 합쳐 canonical text 생성

    Returns:
        (canonical_text, sha256_hash)
    """
    # 섹션 순서 고정
    ordered_sections = ["abstract", "introduction", "methods",
                        "results", "discussion", "conclusion"]

    parts = []
    for section in ordered_sections:
        if section in sections:
            text, _, _ = sections[section]
            parts.append(text)

    canonical_text = "\n\n".join(parts)
    text_hash = hashlib.sha256(canonical_text.encode()).hexdigest()

    return canonical_text, text_hash
```

### 3단계: 섹션 기반 Recursive Chunking

```python
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 토큰 카운터
enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(enc.encode(text))

def chunk_section(
    section_text: str,
    section_offset_start: int,
    chunk_size_tokens: int = 700,
    overlap_tokens: int = 100
) -> list[dict]:
    """
    섹션 내에서 Recursive Chunking 수행

    Returns:
        [
            {
                "text": "...",
                "offset_start": 1250,
                "offset_end": 3400,
                "char_count": 2150
            },
            ...
        ]
    """
    # 토큰 → 문자 변환 (대략 1토큰 = 3.5자)
    chunk_size_chars = int(chunk_size_tokens * 3.5)
    overlap_chars = int(overlap_tokens * 3.5)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " "],
        length_function=count_tokens
    )

    chunk_texts = splitter.split_text(section_text)

    chunks = []
    search_start = 0

    for chunk_text in chunk_texts:
        # 섹션 내에서 청크 위치 찾기
        pos = section_text.find(chunk_text, search_start)
        if pos == -1:
            # 오버랩으로 인해 못 찾을 수 있음 → 앞에서 찾기
            pos = section_text.find(chunk_text)

        offset_start = section_offset_start + pos
        offset_end = offset_start + len(chunk_text)

        chunks.append({
            "text": chunk_text,
            "offset_start": offset_start,
            "offset_end": offset_end,
            "char_count": len(chunk_text)
        })

        # 다음 검색 시작 위치 (오버랩 고려)
        search_start = pos + len(chunk_text) - overlap_chars

    return chunks
```

### 4단계: 청크 메타데이터 생성

```python
@dataclass
class PaperChunk:
    """Weaviate에 저장될 청크 데이터"""
    # 식별자
    chunk_id: str           # pmid:12345678|results|3
    paper_id: str           # pmid:12345678

    # 청크 정보
    section: str            # results
    chunk_index: int        # 3
    text: str               # 원문 텍스트

    # offset (재현용)
    offset_start: int       # 12340
    offset_end: int         # 13280
    text_version: str       # v1

    # Parent 확장용
    parent_expand_chars: int = 500
    section_offset_start: int = 0
    section_offset_end: int = 0

    # 임베딩용 (저장 X, 생성 시에만 사용)
    _embedding_input: str = ""

def create_chunk_metadata(
    paper_id: str,
    title: str,
    year: int,
    section: str,
    chunk_index: int,
    chunk_data: dict,
    section_offset_start: int,
    section_offset_end: int,
    text_version: str = "v1"
) -> PaperChunk:
    """청크 메타데이터 생성"""

    chunk_id = f"{paper_id}|{section}|{chunk_index}"

    # Contextual Embedding용 prefix
    embedding_input = f"""[TITLE] {title}
[SECTION] {section}
[YEAR] {year}
[TEXT] {chunk_data['text']}"""

    return PaperChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        section=section,
        chunk_index=chunk_index,
        text=chunk_data['text'],
        offset_start=chunk_data['offset_start'],
        offset_end=chunk_data['offset_end'],
        text_version=text_version,
        section_offset_start=section_offset_start,
        section_offset_end=section_offset_end,
        _embedding_input=embedding_input
    )
```

---

## Weaviate 저장 스키마

### PaperChunk 필드 매핑

| Chunker 출력 | Weaviate 필드 | 용도 |
|-------------|---------------|------|
| `chunk_id` | `chunkId` | 청크 고유 ID |
| `paper_id` | `paperId` | 논문 ID |
| `section` | `section` | 섹션명 (필터링) |
| `chunk_index` | `chunkIndex` | 섹션 내 순서 |
| `text` | `content` | 청크 텍스트 (BM25) |
| `offset_start` | `offsetStart` | 시작 위치 |
| `offset_end` | `offsetEnd` | 끝 위치 |
| `text_version` | `textVersion` | canonical 버전 |

### 저장 시 주의사항

```python
def store_to_weaviate(chunk: PaperChunk, embedding: list[float]):
    """
    Weaviate 저장

    주의: _embedding_input은 저장하지 않음!
          원문(text)만 저장하고, prefix는 임베딩 시에만 사용
    """
    weaviate_obj = {
        "chunkId": chunk.chunk_id,
        "paperId": chunk.paper_id,
        "section": chunk.section,
        "chunkIndex": chunk.chunk_index,
        "content": chunk.text,  # 원문만!
        "offsetStart": chunk.offset_start,
        "offsetEnd": chunk.offset_end,
        "textVersion": chunk.text_version,
        # ... 기타 메타데이터 (title, year, authors 등)
    }

    # embedding은 벡터로 저장
    paper_chunks.data.insert(
        uuid=generate_uuid(chunk.chunk_id),
        properties=weaviate_obj,
        vector=embedding
    )
```

---

## Parent-Child 런타임 확장

### 검색 후 S3에서 Parent 확장

```python
async def expand_to_parent(
    chunk: PaperChunk,
    s3_client,
    bucket: str,
    prefix: str
) -> str:
    """
    검색된 child 청크를 parent 범위로 확장

    섹션 경계를 존중하며 확장
    """
    # S3에서 canonical text 조회
    canonical_text = await get_canonical_text(
        s3_client, bucket, prefix, chunk.text_version
    )

    # Parent 범위 계산 (섹션 경계 존중)
    parent_start = max(
        chunk.section_offset_start,  # 섹션 시작을 넘지 않음
        chunk.offset_start - chunk.parent_expand_chars
    )
    parent_end = min(
        chunk.section_offset_end,    # 섹션 끝을 넘지 않음
        chunk.offset_end + chunk.parent_expand_chars
    )

    return canonical_text[parent_start:parent_end]
```

---

## 검증 체크리스트

### offset 정확성 검증

```python
def verify_offset(chunk: PaperChunk, canonical_text: str) -> bool:
    """청크의 offset이 정확한지 검증"""
    extracted = canonical_text[chunk.offset_start:chunk.offset_end]
    return extracted == chunk.text
```

### 테스트 케이스

- [ ] 한글/그리스 문자 등 멀티바이트 문자 처리
- [ ] 섹션 경계에서 청크가 넘어가지 않는지
- [ ] 오버랩이 정확히 적용되는지
- [ ] 빈 섹션 처리
- [ ] 매우 짧은 섹션 (청크 1개 미만) 처리

---

## 구현 계획

### Phase 1: 기본 Chunker

- [ ] XML 파서 (lxml) 기반 섹션 추출
- [ ] Canonical text 생성 + S3 저장
- [ ] Recursive Chunking with offset 추적
- [ ] 단위 테스트

### Phase 2: 통합

- [ ] Weaviate 저장 연동
- [ ] 임베딩 생성 (OpenAI 또는 MedCPT)
- [ ] Parent 확장 로직

### Phase 3: 검증

- [ ] 샘플 논문 10편으로 테스트
- [ ] offset 정확성 검증
- [ ] Evidence Reproducibility Rate 측정

---

## How to Run

```bash
cd spikes/OAR-29/yts

# 환경 설정
uv sync

# Chunker 테스트
uv run python src/chunker.py

# 단위 테스트
uv run pytest tests/
```

---

## 참고

- [OAR-18 청킹 설계](../../OAR-18/yts/docs/chunking-design.md)
- [OAR-20 Weaviate 스키마](../../OAR-20/yts/docs/weaviate-스키마-설계.md)
- [OAR-20 PostgreSQL 스키마](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md)
- [LangChain RecursiveCharacterTextSplitter](https://python.langchain.com/docs/modules/data_connection/document_transformers/text_splitters/recursive_text_splitter)
