# OAR-19: 논문 메타데이터 파싱 로직

> **담당**: yts (OAR-95)
>
> **목적**: Europe PMC 데이터를 PostgreSQL 스키마에 맞게 파싱

---

## 빠른 시작

```bash
# 1. 의존성 설치
cd spikes/OAR-19/yts
uv sync

# 2. 데모 앱 실행 (Docker 없이도 가능)
uv run streamlit run demo_app.py

# 3. 브라우저에서 http://localhost:8501 접속
```

### 전체 환경 구성 (DB/S3 포함)

```bash
# 1. 개발 환경 시작 (PostgreSQL + MinIO)
cd spikes/OAR-19/yts/docker
docker compose up -d

# 2. 상태 확인
docker compose ps

# 3. MinIO Console 확인 (선택)
open http://localhost:11901  # minioadmin / minioadmin
```

---

## 데모 페이지

**Streamlit 기반 파이프라인 시각화**

```bash
uv run streamlit run demo_app.py
```

| 단계 | 설명 |
|------|------|
| Step 1 | Europe PMC에서 논문 검색 |
| Step 2 | XML 수집 → 파싱 → 저장 파이프라인 실행 |
| Step 3 | 결과 확인 (메타데이터, 저자, 섹션, Canonical Text) |

---

## 폴더 구조

```
OAR-19/yts/
├── README.md                    # 이 문서
├── demo_app.py                  # Streamlit 데모 앱
├── pyproject.toml               # 의존성
├── docs/
│   └── metadata-parsing-design.md
├── docker/
│   ├── docker-compose.yml       # PostgreSQL + MinIO
│   ├── init.sql                 # DB 스키마
│   └── README.md
├── src/
│   ├── __init__.py              # 모듈 export
│   ├── config.py                # 환경설정
│   ├── models.py                # Author, Section, ParsedPaper
│   ├── preprocess.py            # HTML 엔티티 디코딩
│   ├── parser.py                # XML 파싱 (lxml)
│   ├── storage.py               # DB/S3 저장
│   ├── europe_pmc_client.py     # API 클라이언트 (Raw XML)
│   └── pipeline.py              # 수집→파싱→저장 파이프라인
├── tests/
│   └── test_parser.py           # 11개 테스트
└── examples/
    └── parse_and_save.py
```

---

## 구현 완료 항목

### 1. 전처리 (`preprocess.py`)
- [x] HTML 엔티티 디코딩 (`&#x02010;` → `-`)
- [x] 하이픈 계열 문자 정규화
- [x] 유니코드 NFC 정규화
- [x] 공백 정규화

### 2. XML 파싱 (`parser.py`)
- [x] 저자 추출 (순서, ORCID, 소속, 교신저자)
- [x] 섹션 추출 (Abstract, Introduction, Methods, Results, Discussion)
- [x] **섹션별 offset_start/offset_end 계산** (청킹 연계 핵심)
- [x] canonical_text 생성 및 SHA-256 해시

### 3. 저장 (`storage.py`)
- [x] PostgreSQL 저장 (asyncpg) - papers, paper_authors, paper_sections
- [x] S3 저장 (boto3/MinIO) - canonical/text.txt, metadata.json

### 4. 파이프라인 (`pipeline.py`)
- [x] Europe PMC 검색
- [x] XML 수집 (Raw XML 반환)
- [x] 파싱 → 저장 통합
- [x] 단계별 상태 추적 (on_step 콜백)

### 5. 데모 (`demo_app.py`)
- [x] Streamlit UI
- [x] 실시간 파이프라인 진행 상태 표시
- [x] 파싱 결과 시각화 (저자, 섹션, offset)
- [x] OAR-18 청킹 모듈 연계용 JSON 출력

---

## 테스트

```bash
uv run pytest tests/ -v
# 11 passed
```

---

## OAR-18 청킹 연계

`ParsedPaper.to_chunking_dict()` 메서드로 청킹 모듈에 전달할 데이터 생성:

```python
{
    "paper_id": "pmc:PMC12345678",
    "title": "논문 제목",
    "year": 2024,
    "sections": [
        {
            "name": "abstract",
            "title": "Abstract",
            "text": "초록 내용...",
            "offset_start": 50,
            "offset_end": 500
        },
        ...
    ]
}
```

**offset 기반 On-the-fly Parent 확장** 지원:
- 청크 생성 시 offset_start/offset_end 저장
- RAG 검색 결과에서 근거 재현 시 동적으로 부모 문맥 확장

---

## 관련 문서

- [파싱 로직 설계](./docs/metadata-parsing-design.md)
- [OAR-18 청킹 전략](../../OAR-18/yts/docs/chunking-strategy-rationale.md)
- [OAR-20 PostgreSQL 스키마](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.3.md)
