# Paper ID 및 S3 저장소 설계

> **OAR-19**: 논문 메타데이터 파싱 파이프라인
>
> **버전**: v1.0
>
> **작성일**: 2025-12-26
>
> **기반**: OAR-20 PostgreSQL + S3 스키마 설계 v2.3

---

## 1. Paper ID 설계

### 1.1 핵심 원칙

**PMID(PubMed ID)가 논문의 고유 식별자**

```
같은 논문 "Osimertinib in EGFR-Mutant Lung Cancer":
├── Europe PMC  → PMID: 27959700, PMCID: PMC5765844
├── PubMed      → PMID: 27959700
├── OpenAlex    → PMID: 27959700, OpenAlex ID: W2561234567
└── Semantic Scholar → PMID: 27959700
```

- 어떤 API를 통해 접근하든 **PMID는 동일**
- PMID로 중복 수집 방지 가능
- NLM(National Library of Medicine)에서 부여하는 공식 번호

### 1.2 paper_id 형식

```
{source}:{id}
```

| 우선순위 | 형식 | 예시 | 설명 |
|----------|------|------|------|
| 1 | `pmid:{pmid}` | `pmid:27959700` | PMID 있으면 최우선 |
| 2 | `pmc:{pmcid}` | `pmc:PMC5765844` | PMID 없고 PMCID만 있을 때 |
| 3 | `doi:{doi}` | `doi:10.1056/NEJMoa1713137` | 둘 다 없을 때 fallback |

### 1.3 paper_id 결정 로직

```python
def determine_paper_id(pmid: str | None, pmcid: str | None, doi: str | None) -> str:
    """
    PMID 우선으로 paper_id 결정

    Args:
        pmid: PubMed ID (예: "27959700")
        pmcid: PMC ID (예: "PMC5765844")
        doi: DOI (예: "10.1056/NEJMoa1713137")

    Returns:
        paper_id (예: "pmid:27959700")
    """
    if pmid:
        return f"pmid:{pmid}"
    elif pmcid:
        return f"pmc:{pmcid}"
    elif doi:
        return f"doi:{doi}"
    else:
        raise ValueError("No valid identifier available")
```

### 1.4 중복 방지 전략

```sql
-- papers 테이블
-- paper_id는 UNIQUE (primary identifier)
paper_id VARCHAR(100) UNIQUE NOT NULL,  -- pmid:27959700

-- 개별 ID도 UNIQUE (중복 수집 방지)
CREATE UNIQUE INDEX idx_papers_pmid_unique ON papers(pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_pmcid_unique ON papers(pmcid) WHERE pmcid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_doi_unique ON papers(doi) WHERE doi IS NOT NULL;
```

**수집 시 체크 로직:**
```python
async def should_collect(pmid: str | None, pmcid: str | None) -> bool:
    """이미 수집된 논문인지 확인"""
    if pmid:
        exists = await db.fetchval("SELECT 1 FROM papers WHERE pmid = $1", pmid)
        if exists:
            return False
    if pmcid:
        exists = await db.fetchval("SELECT 1 FROM papers WHERE pmcid = $1", pmcid)
        if exists:
            return False
    return True
```

### 1.5 다중 소스 지원

| 소스 | 제공 ID | paper_id 결정 |
|------|---------|--------------|
| Europe PMC | PMID, PMCID, DOI | PMID 우선 |
| PubMed | PMID, DOI | PMID 사용 |
| OpenAlex | PMID, DOI, OpenAlex ID | PMID 우선 |
| Semantic Scholar | PMID, DOI, S2 ID | PMID 우선 |

```python
# 소스 정보는 source 컬럼에 기록
paper.source = "europe_pmc"  # 어디서 수집했는지
paper.paper_id = "pmid:27959700"  # 식별은 PMID로 통일
```

---

## 2. S3 저장소 설계

### 2.1 버킷 구조

```
s3://oaria-papers/
├── canonical/
│   ├── pmid_27959700/           # paper_id에서 : → _ 변환
│   │   ├── v1.txt               # canonical text v1
│   │   ├── v2.txt               # canonical text v2 (있으면)
│   │   └── versions.json        # 버전 이력 메타데이터
│   └── ...
│
└── raw/                         # 원본 데이터 (백업)
    └── europe_pmc/
        └── PMC5765844.xml
```

### 2.2 S3 경로 변환 규칙

**paper_id → S3 prefix 변환**

```python
def build_canonical_prefix(paper_id: str) -> str:
    """
    paper_id를 S3 safe path로 변환

    Args:
        paper_id: "pmid:27959700"

    Returns:
        "canonical/pmid_27959700/"
    """
    safe_id = paper_id.replace(':', '_')
    return f"canonical/{safe_id}/"
```

| paper_id | S3 prefix |
|----------|-----------|
| `pmid:27959700` | `canonical/pmid_27959700/` |
| `pmc:PMC5765844` | `canonical/pmc_PMC5765844/` |
| `doi:10.1056/NEJMoa1713137` | `canonical/doi_10.1056_NEJMoa1713137/` |

> ⚠️ DOI의 `/`도 `_`로 변환 필요

### 2.3 파일 형식

#### canonical text (v1.txt, v2.txt, ...)

```
# s3://oaria-papers/canonical/pmid_27959700/v1.txt
# → 순수 텍스트만 (헤더 없음, offset 0부터 본문)

Background: Immune checkpoint inhibitors have revolutionized...
(전체 원문 텍스트)
```

#### versions.json (버전 이력)

```json
{
    "paper_id": "pmid:27959700",
    "current_version": "v1",
    "versions": {
        "v1": {
            "created_at": "2025-12-26T10:30:00Z",
            "hash": "sha256:abc123...",
            "length": 45678,
            "source": "europe_pmc",
            "sections": ["abstract", "introduction", "methods", "results", "discussion"]
        }
    }
}
```

### 2.4 버저닝 정책

#### MVP (현재)

```python
canonical_text_version = "v1"  # 항상 고정
```

- 버저닝 로직 없이 단일 버전 운영
- 같은 논문 재수집 시 덮어쓰기 (UPSERT)
- hash 변경 여부만 기록

#### Post-MVP (버저닝 활성화 시)

**버전 업 트리거:**

| 트리거 | 감지 방법 | 버전 업 |
|--------|----------|---------|
| 원본 논문 수정 | 재수집 시 hash 비교 | O |
| Erratum 발표 | Europe PMC `hasErratum` 필드 | O |
| 파싱 로직 변경 | 전체 재처리 필요 | O (배치) |
| 메타데이터만 변경 | hash 동일 | X |

**하위 호환성:**
```python
def get_text_version_for_evidence(evidence: dict, paper: Paper) -> str:
    """
    재현 버전 우선순위:
    1. evidence.text_version (답변 생성 시점 버전)
    2. papers.canonical_text_version (최신 버전, fallback)
    """
    return evidence.get("text_version") or paper.canonical_text_version
```

### 2.5 S3 접근 패턴

```python
import boto3

s3 = boto3.client('s3')
DEFAULT_BUCKET = 'oaria-papers'

def build_canonical_prefix(paper_id: str) -> str:
    """paper_id → S3 prefix"""
    safe_id = paper_id.replace(':', '_').replace('/', '_')
    return f"canonical/{safe_id}/"

def build_canonical_key(prefix: str, version: str) -> str:
    """prefix + version → S3 key"""
    return f"{prefix}{version}.txt"

def get_canonical_text(bucket: str, prefix: str, version: str) -> str:
    """S3에서 canonical text 조회"""
    key = build_canonical_key(prefix, version)
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read().decode('utf-8')

def save_canonical_text(
    paper_id: str,
    text: str,
    version: str = 'v1',
    bucket: str = DEFAULT_BUCKET
) -> tuple[str, str, str]:
    """S3에 canonical text 저장 → (bucket, prefix, version) 반환"""
    prefix = build_canonical_prefix(paper_id)
    key = build_canonical_key(prefix, version)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    return (bucket, prefix, version)
```

---

## 3. 데이터 흐름

### 3.1 수집 → 저장

```
Europe PMC API
      │
      ▼
┌─────────────────────────────────────┐
│ 1. Search API → PMID, PMCID 획득    │
│ 2. Fulltext XML 수집                │
│ 3. 파싱 → canonical_text 생성       │
│ 4. paper_id 결정 (PMID 우선)        │
└─────────────────────────────────────┘
      │
      ├──────────────────────────────┐
      │                              │
      ▼                              ▼
┌─────────────┐              ┌─────────────┐
│ PostgreSQL  │              │     S3      │
│ papers 저장 │              │ canonical/  │
│ - 메타데이터│              │ pmid_xxx/   │
│ - paper_id  │              │   v1.txt    │
│ - prefix    │              │             │
└─────────────┘              └─────────────┘
```

### 3.2 근거 재현 (하이라이트)

```
answer_logs.evidence 조회
      │
      ▼
┌─────────────────────────────────────┐
│ paper_id, offset_start, offset_end  │
│ text_version (재현 버전)             │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ S3에서 해당 버전 text 조회           │
│ text[offset_start:offset_end]       │
│ → 정확한 근거 구간 추출              │
└─────────────────────────────────────┘
```

---

## 4. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2025-12-26 | v1.0 | 초안 작성 - paper_id PMID 우선, S3 버전 관리 설계 |

---

## 5. 참고

- [OAR-20 PostgreSQL 스키마 설계 v2.3](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.3.md)
- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
