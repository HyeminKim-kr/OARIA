# S3 Canonical Text 버저닝 정책

> **OAR-20**: 암 챗봇 서비스 DB 스키마 설계 - 부속 문서
>
> **상태**: Draft (MVP에서는 v1 고정, 추후 적용)
>
> **작성일**: 2025-12-26

---

## 배경

`canonical_text`는 논문 원문을 정규화한 텍스트로, RAG 파이프라인의 기준 데이터입니다.

```
answer_logs.evidence[].text_version = "v1"  ← 답변 생성 시점
papers.canonical_text_version = "v2"        ← 최신 버전
```

과거 답변의 근거를 **정확히 재현**하려면 해당 시점의 버전이 필요합니다.

---

## MVP 정책

```
canonical_text_version = "v1"  # 항상 고정
```

- 버저닝 로직 없이 단일 버전으로 운영
- 같은 논문 재수집 시 덮어쓰기 (UPSERT)
- hash 변경 여부만 기록 (추적용)

---

## 버저닝 트리거 기준 (Post-MVP)

### 1. 원본 논문 변경

| 트리거 | 감지 방법 | 버전 업 |
|--------|----------|---------|
| Erratum 발표 | Europe PMC `hasErratum` 필드 | O |
| 논문 내용 수정 | 재수집 시 hash 비교 | O |
| 메타데이터만 변경 | 재수집 시 hash 동일 | X |

**감지 로직:**
```python
def should_create_new_version(existing_hash: str, new_hash: str) -> bool:
    """canonical_text hash 비교로 버전 업 결정"""
    return existing_hash != new_hash
```

### 2. 파싱/전처리 로직 변경

| 변경 유형 | 영향 | 버전 업 |
|----------|------|---------|
| HTML entity 처리 변경 | canonical_text 변경 | O (전체) |
| 섹션 추출 로직 변경 | canonical_text 변경 | O (전체) |
| 공백 정규화 변경 | canonical_text 변경 | O (전체) |
| 메타데이터 파싱 변경 | canonical_text 불변 | X |

**주의**: 파싱 로직 변경 시 **전체 논문 재처리** 필요 → 배치 작업

### 3. 수동 트리거

- 관리자가 특정 논문의 canonical_text를 수동 수정
- 데이터 정제 작업 후 일괄 버전 업

---

## 버전 업 절차

### 단일 논문 버전 업

```python
async def upgrade_paper_version(paper_id: str, new_text: str) -> str:
    """
    1. 현재 버전 확인
    2. 새 버전 번호 생성
    3. S3에 새 파일 저장
    4. DB 업데이트
    """
    paper = await get_paper(paper_id)
    current_version = paper.canonical_text_version  # "v1"
    new_version = increment_version(current_version)  # "v2"

    # S3 저장 (기존 파일 유지, 새 파일 추가)
    # canonical/{paper_id}/v1.txt ← 유지
    # canonical/{paper_id}/v2.txt ← 신규
    await s3.save(
        key=f"canonical/{paper_id}/{new_version}.txt",
        body=new_text
    )

    # DB 업데이트
    await update_paper(
        paper_id=paper_id,
        canonical_text_version=new_version,
        canonical_text_hash=compute_hash(new_text),
        canonical_text_length=len(new_text)
    )

    return new_version
```

### 전체 논문 일괄 버전 업 (파싱 로직 변경 시)

```python
async def batch_upgrade_all_papers(dry_run: bool = True):
    """
    파싱 로직 변경 후 전체 논문 재처리

    1. 모든 논문 조회
    2. 원본 XML 재파싱
    3. hash 비교 → 변경된 것만 버전 업
    4. 로그 기록
    """
    papers = await get_all_papers()
    upgraded = []

    for paper in papers:
        # 원본 XML 재수집 또는 raw/ 에서 로드
        xml = await get_raw_xml(paper.paper_id)
        new_text = parse_canonical_text(xml)
        new_hash = compute_hash(new_text)

        if new_hash != paper.canonical_text_hash:
            if not dry_run:
                await upgrade_paper_version(paper.paper_id, new_text)
            upgraded.append(paper.paper_id)

    return {
        "total": len(papers),
        "upgraded": len(upgraded),
        "dry_run": dry_run,
        "paper_ids": upgraded
    }
```

---

## 하위 호환성

### 근거 재현 시 버전 결정

```python
def get_text_version_for_evidence(evidence: dict, paper: Paper) -> str:
    """
    재현 버전 우선순위:
    1. evidence.text_version (답변 생성 시점 버전)
    2. papers.canonical_text_version (최신 버전, fallback)
    """
    return evidence.get("text_version") or paper.canonical_text_version
```

### S3 파일 유지 정책

| 정책 | 설명 |
|------|------|
| **Append-only** | 기존 버전 파일 수정/삭제 금지 |
| **보존 기간** | 최소 2년 (answer_logs 보존 기간과 동일) |
| **Glacier 이관** | 1년 이상 미참조 버전은 Glacier로 이관 가능 |

---

## 버전 형식

```
v1, v2, v3, ...  # 단순 증가
```

- 시맨틱 버저닝 불필요 (breaking change 개념 없음)
- 숫자만으로 순서 보장

---

## 모니터링

### 버전 업 이력 추적

```sql
-- papers 테이블에 버전 이력 조회용 뷰
CREATE VIEW v_paper_version_history AS
SELECT
    paper_id,
    canonical_text_version,
    canonical_text_hash,
    updated_at
FROM papers
ORDER BY updated_at DESC;
```

### 알림 조건

| 조건 | 알림 |
|------|------|
| 일일 버전 업 > 100건 | Slack 알림 |
| 단일 논문 버전 > 5 | 검토 필요 (이상 징후) |

---

## 적용 시점

버저닝 활성화 조건:

1. **answer_logs 누적 > 10,000건** - 과거 답변 재현 필요성 증가
2. **파싱 로직 주요 변경 예정** - 하위 호환성 필요
3. **사용자 피드백** - "예전 답변이랑 근거가 다르다" 이슈 발생

---

## 참고

- [postgresql-스키마-설계-v2.3.md](./postgresql-스키마-설계-v2.3.md) - S3 저장 구조
- [Europe PMC API](https://europepmc.org/RestfulWebService) - hasErratum 필드
