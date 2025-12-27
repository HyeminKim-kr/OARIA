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

### 식별자 우선순위

```
1. PMID (가장 신뢰도 높음)
2. PMCID
3. DOI
```

### 매칭 로직

```python
def is_duplicate(new_paper, existing_papers):
    """
    하나라도 매칭되면 중복으로 판단
    """
    for existing in existing_papers:
        if new_paper.pmid and new_paper.pmid == existing.pmid:
            return True, "pmid", existing
        if new_paper.pmcid and new_paper.pmcid == existing.pmcid:
            return True, "pmcid", existing
        if new_paper.doi and new_paper.doi == existing.doi:
            return True, "doi", existing
    return False, None, None
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
