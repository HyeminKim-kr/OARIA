# 중복 논문 검출 시나리오

> **OAR-23**: 중복 논문 검출 및 제거 로직
>
> **작성일**: 2025-12-27

---

## 개요

논문 수집 파이프라인에서 발생할 수 있는 중복 시나리오를 정리하고, 각 시나리오별 기대 동작을 정의합니다.

---

## 시나리오 목록

### 시나리오 1: 여러 소스에서 수집

**상황**
```
팀원 A: Europe PMC에서 "lung cancer" 수집
팀원 B: PubMed에서 "lung cancer" 수집

→ 같은 PMID 논문이 양쪽에 존재
```

**원인**: 같은 논문이 여러 데이터베이스에 등록됨

**기대 동작**: 스킵 (먼저 저장된 것 유지)

---

### 시나리오 2: 검색어 겹침 (같은 배치 내)

**상황**
```
검색 1: "lung cancer immunotherapy" → 100건
검색 2: "checkpoint inhibitor NSCLC" → 80건

→ 30건이 양쪽 검색 결과에 포함
```

**원인**: 다른 검색어지만 같은 논문이 매칭됨

**기대 동작**: 스킵 (배치 내 중복 제거)

---

### 시나리오 3: 주기적 재수집

**상황**
```
1주차: "lung cancer 2025" 수집 → 500건 저장
2주차: 같은 쿼리 재실행 → 520건 결과

→ 기존 500건 + 신규 20건
```

**원인**: 정기적인 업데이트 수집

**기대 동작**:
- 기존 500건 → 스킵
- 신규 20건 → 저장

---

### 시나리오 4: 원본 논문 수정 (Erratum/Correction)

**상황**
```
기존 저장: PMC123456 (2025-01-01 버전)
재수집: PMC123456 (2025-01-15 수정됨)

→ PMID는 같지만 내용이 변경됨
```

**원인**: 출판사에서 논문 내용 수정 (오류 정정, 보충 자료 추가 등)

**기대 동작**: 업데이트 (변경 감지 후)

**변경 감지 방법**: `raw_xml_hash` 비교

---

### 시나리오 5: 파서 버전 업그레이드

**상황**
```
기존: parser_version 1.0.0으로 파싱된 1000건
변경: parser_version 1.1.0 (섹션 추출 로직 개선)

→ 원본은 안 바뀌었지만 재파싱 필요
```

**원인**: 파싱 로직 개선, 버그 수정

**기대 동작**: 강제 업데이트 (의도된 재처리)

**변경 감지 방법**: `parser_version` 비교

---

### 시나리오 6: 식별자 불일치

**상황**
```
시점 1: DOI만 있는 논문 저장 (doi:10.1234/example)
시점 2: 같은 논문에 PMID 부여됨 (pmid:12345678)

→ 같은 논문이 다른 paper_id로 인식될 위험
```

**원인**:
- 신규 논문은 DOI만 먼저 부여됨
- PubMed 등록 후 PMID 부여 (수 주 ~ 수 개월 소요)

**기대 동작**: 병합 또는 연결 (복잡한 케이스)

**비고**: MVP에서는 제외, Phase 2에서 처리

---

## 시나리오별 처리 전략 요약

| # | 시나리오 | 원인 | 기대 동작 | MVP |
|---|---------|------|----------|-----|
| 1 | 여러 소스 수집 | 같은 논문, 다른 API | 스킵 | ✅ |
| 2 | 검색어 겹침 | 같은 논문, 같은 배치 | 스킵 | ✅ |
| 3 | 주기적 재수집 | 같은 논문, 변경 없음 | 스킵 | ✅ |
| 4 | 원본 수정 | 같은 논문, 내용 변경 | 업데이트 | ✅ |
| 5 | 파서 업그레이드 | 같은 논문, 파서 변경 | 강제 업데이트 | ✅ |
| 6 | 식별자 불일치 | 같은 논문, 다른 ID | 병합 | ❌ (Phase 2) |

---

## 중복 판별 기준

### 배경 지식

**PMID (PubMed ID)**
- PubMed의 **레코드(인용 record)** 단위 고유 ID
- 같은 논문이라도 PubMed에 다른 레코드가 있으면 PMID가 다를 수 있음
- Erratum/Retraction/Correction은 별도 PMID 부여됨

**PMCID (PubMed Central ID)**
- PMC의 풀텍스트 아카이브 레코드 ID
- 버전 표기가 붙는 경우 있음 (예: `PMC123456.1`) → 정규화 필요

**DOI (Digital Object Identifier)**
- Crossref 등에서 콘텐츠 아이템을 식별하는 PID
- **논문 1편만이 아니라** 정정/데이터셋/버전 등에도 붙을 수 있음
- 출판사 메타데이터 실수/수정으로 예외 케이스 발생 가능

---

### 3단계 중복 판별 체계

| 단계 | 분류 | 설명 | 처리 |
|------|------|------|------|
| 1 | **중복 확정** | 같은 레코드임이 확실 | 자동 스킵/업데이트 |
| 2 | **중복 후보** | 같은 논문일 가능성 높음 | 가드레일 적용 후 처리 |
| 3 | **연관 관계** | 같은 논문은 아니지만 관련됨 | 링크로 연결 (병합 X) |

---

### 1단계: 중복 확정 (Definite Duplicate)

**PMID 동일**
```python
if normalize_pmid(new.pmid) == normalize_pmid(existing.pmid):
    return DuplicateResult(
        status="DEFINITE_DUPLICATE",
        matched_by="pmid",
        action="SKIP_OR_UPDATE"
    )
```

**PMCID 동일** (정규화 후)
```python
def normalize_pmcid(pmcid: str) -> str:
    """PMC123456.1 → PMC123456 (버전 제거)"""
    if not pmcid:
        return None
    pmcid = pmcid.upper()
    if not pmcid.startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    # 버전 제거: PMC123456.1 → PMC123456
    return pmcid.split(".")[0]

if normalize_pmcid(new.pmcid) == normalize_pmcid(existing.pmcid):
    return DuplicateResult(
        status="DEFINITE_DUPLICATE",
        matched_by="pmcid",
        action="SKIP_OR_UPDATE"
    )
```

---

### 2단계: 중복 후보 (Probable Duplicate)

**DOI 동일 → 가드레일 적용**

DOI가 같아도 바로 중복 확정하지 않고, 추가 검증:

```python
def check_doi_duplicate(new_paper, existing) -> DuplicateResult:
    """DOI 매칭 시 가드레일 적용"""

    if normalize_doi(new_paper.doi) != normalize_doi(existing.doi):
        return None  # DOI 불일치

    # 가드레일 1: 레코드 타입 확인
    # Erratum/Retraction/Correction은 별도 레코드로 처리
    correction_types = ["erratum", "retraction", "correction",
                        "expression of concern", "comment", "reply"]

    new_type = (new_paper.publication_type or "").lower()
    existing_type = (existing.publication_type or "").lower()

    if any(ct in new_type for ct in correction_types):
        return DuplicateResult(
            status="RELATED_RECORD",
            matched_by="doi",
            relation_type=new_type,
            action="LINK_NOT_MERGE"
        )

    # 가드레일 2: 메타데이터 불일치 검사
    # 제목/저자/연도가 크게 다르면 검토 큐로
    if not metadata_similar(new_paper, existing):
        return DuplicateResult(
            status="REVIEW_NEEDED",
            matched_by="doi",
            reason="metadata_mismatch",
            action="SEND_TO_REVIEW_QUEUE"
        )

    # 가드레일 통과 → 중복 후보 확정
    return DuplicateResult(
        status="PROBABLE_DUPLICATE",
        matched_by="doi",
        action="SKIP_OR_UPDATE"
    )
```

**메타데이터 유사도 검사**
```python
def metadata_similar(new_paper, existing, threshold=0.8) -> bool:
    """제목/저자/연도 기반 유사도 검사"""

    # 연도 체크 (2년 이상 차이나면 의심)
    if new_paper.year and existing.year:
        if abs(new_paper.year - existing.year) > 1:
            return False

    # 제목 유사도 (정규화 후 비교)
    title_sim = similarity(
        normalize_title(new_paper.title),
        normalize_title(existing.title)
    )
    if title_sim < threshold:
        return False

    # 1저자 비교
    new_first = get_first_author(new_paper)
    existing_first = get_first_author(existing)
    if new_first and existing_first:
        if not author_similar(new_first, existing_first):
            return False

    return True
```

---

### 3단계: 연관 관계 (Related Record)

**병합하지 않고 링크로 연결해야 하는 케이스:**

| 타입 | 설명 | 처리 |
|------|------|------|
| Erratum | 원문의 오류 정정 공지 | `original_pmid` 필드로 연결 |
| Retraction | 철회 공지 | `retracted_pmid` 필드로 연결 |
| Correction | 내용 수정 공지 | `corrects_pmid` 필드로 연결 |
| Comment | 논문에 대한 코멘트 | `comment_on_pmid` 필드로 연결 |
| Reply | 코멘트에 대한 답변 | `reply_to_pmid` 필드로 연결 |

```python
def handle_related_record(new_paper, existing) -> SaveResult:
    """연관 레코드 처리 - 별도 저장 + 링크"""

    # 새 레코드로 저장 (병합 X)
    new_id = await save_paper(new_paper)

    # 연관 관계 저장
    await save_relation(
        source_id=new_id,
        target_id=existing.id,
        relation_type=new_paper.publication_type,  # "erratum", "retraction" 등
    )

    return SaveResult(
        status="SAVED_AS_RELATED",
        paper_id=new_paper.paper_id,
        related_to=existing.paper_id
    )
```

---

### 4단계: Fallback - Fuzzy 매칭 (ID 없는 경우)

**세 ID 모두 없거나 불완전한 경우:**

```python
def fuzzy_duplicate_check(new_paper, existing_papers) -> DuplicateResult:
    """ID 없을 때 메타데이터 기반 fuzzy 매칭"""

    for existing in existing_papers:
        score = calculate_similarity_score(new_paper, existing)

        if score >= 0.95:  # 높은 확신
            return DuplicateResult(
                status="PROBABLE_DUPLICATE",
                matched_by="fuzzy",
                confidence=score,
                action="SKIP_OR_UPDATE"
            )
        elif score >= 0.8:  # 중간 확신
            return DuplicateResult(
                status="REVIEW_NEEDED",
                matched_by="fuzzy",
                confidence=score,
                action="SEND_TO_REVIEW_QUEUE"
            )

    return DuplicateResult(status="NEW", action="SAVE")


def calculate_similarity_score(new_paper, existing) -> float:
    """
    유사도 점수 계산 (0.0 ~ 1.0)

    가중치:
    - 제목: 40%
    - 1저자: 25%
    - 저널: 15%
    - 연도: 10%
    - 권/호/페이지: 10%
    """
    score = 0.0

    # 제목 (40%)
    title_sim = similarity(
        normalize_title(new_paper.title),
        normalize_title(existing.title)
    )
    score += title_sim * 0.4

    # 1저자 (25%)
    author_sim = author_similarity(
        get_first_author(new_paper),
        get_first_author(existing)
    )
    score += author_sim * 0.25

    # 저널 (15%)
    journal_sim = similarity(
        normalize_journal(new_paper.journal),
        normalize_journal(existing.journal)
    )
    score += journal_sim * 0.15

    # 연도 (10%)
    if new_paper.year and existing.year:
        if new_paper.year == existing.year:
            score += 0.1
        elif abs(new_paper.year - existing.year) == 1:
            score += 0.05

    # 권/호/페이지 (10%)
    if all([new_paper.volume, new_paper.issue, new_paper.pages,
            existing.volume, existing.issue, existing.pages]):
        if (new_paper.volume == existing.volume and
            new_paper.issue == existing.issue and
            new_paper.pages == existing.pages):
            score += 0.1

    return score
```

---

### 정규화 함수

```python
def normalize_pmid(pmid: str) -> str:
    """PMID 정규화: 숫자만 추출"""
    if not pmid:
        return None
    return re.sub(r'\D', '', str(pmid))


def normalize_pmcid(pmcid: str) -> str:
    """PMCID 정규화: PMC 접두사 + 버전 제거"""
    if not pmcid:
        return None
    pmcid = pmcid.upper().strip()
    if not pmcid.startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    return pmcid.split(".")[0]  # 버전 제거


def normalize_doi(doi: str) -> str:
    """DOI 정규화: 소문자 + URL 제거"""
    if not doi:
        return None
    doi = doi.lower().strip()
    # URL 형식 제거
    doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
    return doi


def normalize_title(title: str) -> str:
    """제목 정규화: 소문자 + 특수문자 제거"""
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)  # 특수문자 제거
    title = re.sub(r'\s+', ' ', title)      # 연속 공백 제거
    return title.strip()


def normalize_journal(journal: str) -> str:
    """저널명 정규화: 약어 통일"""
    if not journal:
        return ""
    journal = journal.lower().strip()
    # 흔한 약어 통일
    replacements = {
        "j.": "journal",
        "j ": "journal ",
        "int.": "international",
        "am.": "american",
        "eur.": "european",
    }
    for abbr, full in replacements.items():
        journal = journal.replace(abbr, full)
    return journal
```

---

### 전체 중복 검사 흐름

```python
async def check_duplicate(new_paper, db) -> DuplicateResult:
    """
    중복 검사 메인 로직

    우선순위:
    1. PMID 매칭 → 중복 확정
    2. PMCID 매칭 → 중복 확정
    3. DOI 매칭 → 가드레일 적용
    4. Fuzzy 매칭 → ID 없을 때 fallback
    """

    # 1. PMID 체크 (중복 확정)
    if new_paper.pmid:
        existing = await db.find_by_pmid(normalize_pmid(new_paper.pmid))
        if existing:
            return DuplicateResult(
                status="DEFINITE_DUPLICATE",
                matched_by="pmid",
                existing=existing
            )

    # 2. PMCID 체크 (중복 확정)
    if new_paper.pmcid:
        existing = await db.find_by_pmcid(normalize_pmcid(new_paper.pmcid))
        if existing:
            return DuplicateResult(
                status="DEFINITE_DUPLICATE",
                matched_by="pmcid",
                existing=existing
            )

    # 3. DOI 체크 (가드레일 적용)
    if new_paper.doi:
        existing = await db.find_by_doi(normalize_doi(new_paper.doi))
        if existing:
            result = check_doi_duplicate(new_paper, existing)
            if result:
                return result

    # 4. Fuzzy 매칭 (ID 없을 때)
    if not any([new_paper.pmid, new_paper.pmcid, new_paper.doi]):
        candidates = await db.find_by_title_year(
            normalize_title(new_paper.title),
            new_paper.year
        )
        if candidates:
            return fuzzy_duplicate_check(new_paper, candidates)

    # 신규 논문
    return DuplicateResult(status="NEW", action="SAVE")
```

---

### 처리 결과 타입

```python
@dataclass
class DuplicateResult:
    status: str          # NEW, DEFINITE_DUPLICATE, PROBABLE_DUPLICATE,
                         # RELATED_RECORD, REVIEW_NEEDED
    matched_by: str      # pmid, pmcid, doi, fuzzy
    existing: dict       # 매칭된 기존 레코드
    action: str          # SAVE, SKIP_OR_UPDATE, LINK_NOT_MERGE,
                         # SEND_TO_REVIEW_QUEUE
    confidence: float    # fuzzy 매칭 시 신뢰도
    relation_type: str   # erratum, retraction 등 (연관 관계 시)
```

---

## 변경 감지 로직

```python
def detect_change_type(existing, new_paper):
    """
    중복인 경우, 변경 유형 판별
    """
    if existing.raw_xml_hash != new_paper.raw_xml_hash:
        return "UPSTREAM_CHANGE"  # 원본 논문 수정됨

    if existing.parser_version != new_paper.parser_version:
        return "PARSER_CHANGE"   # 파서 버전 변경

    return "NO_CHANGE"           # 변경 없음
```

---

## 처리 옵션

| 옵션 | 설명 | 사용 시점 |
|------|------|----------|
| `SKIP` | 스킵 (아무것도 안 함) | 변경 없을 때 |
| `UPDATE_IF_CHANGED` | 변경 시에만 업데이트 | 기본값 |
| `FORCE_UPDATE` | 무조건 덮어쓰기 | 파서 재처리 시 |

---

## 현재 구현 상태 (OAR-19 기준)

### ✅ 구현 완료

| 항목 | 설명 | 위치 |
|------|------|------|
| `paper_id` UNIQUE | 기본 중복 방지 | `init.sql:17` |
| `pmid` UNIQUE INDEX | PMID 중복 방지 | `init.sql:57` |
| `pmcid` UNIQUE INDEX | PMCID 중복 방지 | `init.sql:58` |
| `doi` UNIQUE INDEX | DOI 중복 방지 | `init.sql:59` |
| `ON CONFLICT → UPDATE` | 중복 시 자동 업데이트 | `storage.py:59-70` |
| `raw_xml_hash` 저장 | 원본 변경 추적용 | `storage.py:68` |
| `parser_version` 저장 | 파서 변경 추적용 | `storage.py:69` |

**현재 동작 방식**:
```sql
-- 중복 INSERT 시 무조건 UPDATE (변경 여부 확인 없이)
ON CONFLICT (paper_id) DO UPDATE SET
    title = EXCLUDED.title,
    ...
    raw_xml_hash = EXCLUDED.raw_xml_hash,
    parser_version = EXCLUDED.parser_version,
    updated_at = NOW()
```

### ❌ 미구현 (추가 필요)

| 항목 | 설명 | 우선순위 |
|------|------|----------|
| 사전 중복 체크 | INSERT 전 DB 조회로 불필요한 파싱 방지 | 높음 |
| 변경 감지 로직 | hash 비교 후 SKIP/UPDATE 결정 | 높음 |
| 처리 옵션 선택 | SKIP / UPDATE_IF_CHANGED / FORCE | 중간 |
| 배치 필터링 | 대량 처리 시 한 번에 중복 체크 | 중간 |
| 결과 리포팅 | 신규/중복/변경 통계 | 낮음 |

---

## 구현 계획

### Phase 1: 변경 감지 기반 저장 (권장)

현재 `ON CONFLICT`를 개선하여 변경 시에만 UPDATE:

```sql
-- 개선안: 변경된 경우에만 UPDATE
ON CONFLICT (paper_id) DO UPDATE SET
    title = EXCLUDED.title,
    ...
    updated_at = NOW()
WHERE papers.raw_xml_hash != EXCLUDED.raw_xml_hash
   OR papers.parser_version != EXCLUDED.parser_version
```

### Phase 2: 사전 중복 체크 API

INSERT 전에 미리 확인하여 불필요한 작업 방지:

```python
async def check_and_save(paper: ParsedPaper, strategy: str = "UPDATE_IF_CHANGED") -> SaveResult:
    """
    중복 체크 후 전략에 따라 저장

    Args:
        paper: 저장할 논문
        strategy: SKIP | UPDATE_IF_CHANGED | FORCE_UPDATE

    Returns:
        SaveResult(status="NEW" | "UPDATED" | "SKIPPED", paper_id=...)
    """
    existing = await get_existing_paper(paper.pmid, paper.pmcid, paper.doi)

    if existing is None:
        await save_paper(paper)
        return SaveResult(status="NEW", paper_id=paper.paper_id)

    if strategy == "SKIP":
        return SaveResult(status="SKIPPED", paper_id=existing.paper_id)

    if strategy == "FORCE_UPDATE":
        await save_paper(paper)
        return SaveResult(status="UPDATED", paper_id=paper.paper_id)

    # UPDATE_IF_CHANGED (기본값)
    change_type = detect_change_type(existing, paper)

    if change_type == "NO_CHANGE":
        return SaveResult(status="SKIPPED", paper_id=existing.paper_id)
    else:
        await save_paper(paper)
        return SaveResult(status="UPDATED", paper_id=paper.paper_id, change_type=change_type)
```

### Phase 3: 배치 사전 필터링

대량 수집 시 API 호출 전에 기존 데이터 확인:

```python
async def filter_new_papers(paper_ids: list[str]) -> list[str]:
    """
    DB에 없는 paper_id만 반환

    Args:
        paper_ids: 수집 예정 ID 목록 (예: ["PMC123", "PMC456", ...])

    Returns:
        DB에 없는 ID만 필터링된 목록
    """
    query = "SELECT pmcid FROM papers WHERE pmcid = ANY($1)"
    existing = await conn.fetch(query, paper_ids)
    existing_set = {row["pmcid"] for row in existing}

    return [pid for pid in paper_ids if pid not in existing_set]
```

**사용 예시**:
```python
# 검색 결과 100건 중 DB에 없는 것만 수집
search_results = await search_europe_pmc("lung cancer", limit=100)
paper_ids = [r.pmcid for r in search_results]

new_ids = await filter_new_papers(paper_ids)  # 30건만 신규
print(f"신규: {len(new_ids)}, 기존: {len(paper_ids) - len(new_ids)}")

# 신규만 XML 다운로드 및 파싱
for pmcid in new_ids:
    xml = await fetch_fulltext(pmcid)
    paper = parse_fulltext_xml(xml)
    await save_paper(paper)
```

---

## 시나리오별 구현 매핑

| 시나리오 | 필요 기능 | 현재 | Phase |
|---------|----------|------|-------|
| 1. 여러 소스 수집 | UNIQUE INDEX | ✅ | - |
| 2. 검색어 겹침 | 배치 내 중복 제거 | ❌ | 3 |
| 3. 주기적 재수집 | 사전 필터링 | ❌ | 3 |
| 4. 원본 수정 | 변경 감지 UPDATE | ❌ | 1 |
| 5. 파서 업그레이드 | FORCE_UPDATE 옵션 | ❌ | 2 |
| 6. 식별자 불일치 | ID 병합 로직 | ❌ | 별도 |

---

## 참고

- [OAR-19 Hash 설계](../../OAR-19/yts/docs/hash-design-improvements.md)
- [OAR-20 PostgreSQL 스키마](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.4.md)
