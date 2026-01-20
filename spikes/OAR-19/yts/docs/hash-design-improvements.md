# Hash 설계 개선 방안

> **OAR-19**: 논문 메타데이터 파싱 파이프라인 - 부속 문서
>
> **상태**: ✅ 스키마 반영 완료 (OAR-20 v2.4)
>
> **작성일**: 2025-12-27
>
> **반영일**: 2025-12-27

---

## 1. 현재 설계 분석

### 1.1 장점 (유지)

| 항목 | 설명 |
|------|------|
| 원문 변경 감지 | canonical_text가 바뀌면 hash가 바뀜 → 단순하고 강력 |
| 불필요한 재처리 방지 | 메타데이터만 변경 시 hash 유지 → 재청킹/재인덱싱 비용 절감 |
| 근거 재현 | text_version으로 과거 답변의 정확한 근거 재현 가능 |

### 1.2 현재 한계

**변경 원인 구분 불가**

```
canonical_text_hash 변경됨
    ├── 원본 논문이 수정됨? (Europe PMC에서)
    └── 우리 파서가 바뀜?   (코드 변경)
         → 구분 불가 ❌
```

파서/정규화 로직이 바뀌면 같은 소스여도 canonical_text가 달라져서 hash가 바뀜.
이건 버그가 아니라 "의도된 재처리"일 수 있지만, 운영에서는 원인 구분이 필요함.

---

## 2. 개선 방안

### 2.1 추가 컬럼 ✅ (반영 완료)

> **스키마 반영**: OAR-19 `docker/init.sql`, OAR-20 `postgresql-스키마-설계-v2.4.md`

```sql
-- papers 테이블에 추가됨
raw_xml_hash VARCHAR(64),         -- SHA256 (원본 XML bytes 기준)
parser_version VARCHAR(20) DEFAULT '1.0.0',  -- 파싱 로직 버전
```

| 컬럼 | 설명 | 예시 |
|------|------|------|
| `raw_xml_hash` | 원본 XML bytes SHA256 | `abc123...` |
| `parser_version` | 파싱 로직 버전 | `1.0.0`, `1.1.0` |

### 2.2 변경 감지 로직

```python
def detect_change_type(
    existing_raw_hash: str,
    existing_parser_version: str,
    new_raw_hash: str,
    new_parser_version: str,
    existing_canonical_hash: str,
    new_canonical_hash: str,
) -> str:
    """변경 유형 판별"""

    if existing_canonical_hash == new_canonical_hash:
        return "NO_CHANGE"

    if existing_raw_hash != new_raw_hash:
        return "UPSTREAM_CHANGE"  # 원본 논문이 수정됨

    if existing_parser_version != new_parser_version:
        return "PARSER_CHANGE"   # 파서 로직 변경으로 인한 재처리

    return "UNKNOWN_CHANGE"      # 예상치 못한 변경 (디버깅 필요)
```

### 2.3 변경 유형별 대응

| 변경 유형 | 원인 | 대응 |
|----------|------|------|
| `UPSTREAM_CHANGE` | Europe PMC에서 논문 수정 | 버전 업 (v1→v2) + 알림 |
| `PARSER_CHANGE` | 우리 파서 로직 변경 | 일괄 재처리 (배치) |
| `UNKNOWN_CHANGE` | 원인 불명 | 로그 기록 + 검토 |

---

## 3. 해시 대상 일관성

### 3.1 원칙

> **해시는 "S3에 저장한 vN.txt 그 자체(정확히 동일한 문자열/바이트)"로 계산**

### 3.2 현재 구현 확인 필요

| 항목 | 설계 문서 | 현재 구현 | 상태 |
|------|----------|----------|------|
| S3 저장 포맷 | 순수 텍스트 (헤더 없음) | `[TITLE]...[ABSTRACT]...` 헤더 포함 | ⚠️ 확인 필요 |
| hash 대상 | S3 저장 파일과 동일 | canonical_text 전체 | ✅ 일치 |

**결정 필요:**
- 옵션 A: 헤더 포함 유지 (현재) → offset 계산 시 헤더 고려 필요
- 옵션 B: 순수 텍스트로 변경 → offset 계산 단순화, 하지만 구조 변경 필요

### 3.3 메타데이터 해시 분리 (선택적)

```sql
-- 메타데이터 변경만 추적하고 싶을 때
ALTER TABLE papers ADD COLUMN metadata_hash VARCHAR(64);
```

```python
def compute_metadata_hash(paper: ParsedPaper) -> str:
    """메타데이터만으로 해시 계산"""
    metadata_str = f"{paper.title}|{paper.abstract}|{paper.journal}|{paper.year}"
    return hashlib.sha256(metadata_str.encode()).hexdigest()
```

---

## 4. 재인덱싱 전략

### 4.1 버전 기반 청크 관리

```
canonical_text 버전 업 (v1 → v2)
    │
    ├── 새 청크 생성 (text_version = v2)
    │
    └── 기존 청크 유지 (text_version = v1)  ← 삭제 금지! 재현용
```

### 4.2 답변 생성 시

```python
def get_chunks_for_answer(paper_id: str) -> list[Chunk]:
    """최신 버전 청크만 사용"""
    paper = get_paper(paper_id)
    return get_chunks(paper_id, text_version=paper.canonical_text_version)

def get_chunks_for_evidence_replay(evidence: dict) -> list[Chunk]:
    """과거 답변 재현 시 해당 버전 청크 사용"""
    return get_chunks(
        paper_id=evidence["paper_id"],
        text_version=evidence["text_version"]
    )
```

---

## 5. 마이그레이션 계획

### Phase 1: MVP (현재) ✅
- `canonical_text_hash` 기록만 (추적용)
- 버전은 `v1` 고정
- **`raw_xml_hash`, `parser_version` 스키마 추가 완료** (2025-12-27)

### Phase 2: 구현 예정
1. ~~`raw_xml_hash`, `parser_version` 컬럼 추가~~ ✅ 완료
2. 기존 데이터 백필 (가능한 경우)
3. 변경 감지 로직 구현 (코드)

### Phase 3: 운영 안정화
1. 모니터링 대시보드 구축
2. 알림 설정 (일일 변경 > 100건 등)
3. S3 텍스트 포맷 최종 결정

---

## 6. 참고

- [paper-id-and-storage-design.md](./paper-id-and-storage-design.md) - Paper ID 및 S3 저장소 설계
- [s3-versioning-policy.md](./s3-versioning-policy.md) - 버저닝 트리거 기준
- [OAR-20 PostgreSQL 스키마 설계 v2.4](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.4.md) - 원본 스키마 설계
