# OAR-9: 암 논문 자동 Batch 수집기

> **담당**: tsy
>
> Epic: [F-02] 암 논문 자동 Batch 수집기

---

## 목표

PubMed/PMC API를 통해 암 관련 논문을 자동 수집하고, RAG 시스템의 지식 베이스로 활용할 수 있도록 구축한다.

**수집 목표:**
- 초기: 50,000건
- 최종: 100,000건+

---

## 스파이크 진행 상황

- [x] 데이터 소스 조사 (PubMed, Europe PMC, OpenAlex)
- [x] 수집 전략 결정 (Europe PMC 단일 소스)
- [x] Vector DB 비교 분석
- [x] 프로세스 흐름도 작성
- [ ] 대량 수집 테스트 (MVP 단계)

---

## 핵심 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| **데이터 소스** | Europe PMC | 전문(Full-text) 무료 제공 |
| **수집 범위** | Open Access만 | 합법적 전문 수집 가능 |
| **검색 쿼리** | `neoplasms AND OPEN_ACCESS:Y` | MeSH 표준 용어 |
| **타겟 사용자** | 종양학 연구자 | 전문 텍스트 필요 |

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| [데이터 수집 전략](./데이터-수집-전략.md) | 수집 전략, 쿼리, 데이터 스키마 |
| [암 논문 크롤링 조사](./암-논문-크롤링.md) | PubMed, Europe PMC, OpenAlex 비교 |
| [프로세스 흐름도](./프로세스-흐름도.md) | 전체 파이프라인 다이어그램 |
| [Vector DB 비교](./vector-db-comparison.md) | pgvector, Pinecone, Weaviate 등 비교 |

---

## 태스크 구조 (Jira)

```
OAR-9 (Epic): 암 논문 자동 Batch 수집기
├── OAR-20: [01] PostgreSQL 논문 스키마 설계 및 구현
├── OAR-18: [02] PubMed API 연동 구현
├── OAR-19: [03] 논문 메타데이터 파싱 로직 구현
├── OAR-23: [04] 중복 논문 검출 및 제거 로직
├── OAR-22: [05] Rate Limit 처리 및 재시도 로직 구현
└── OAR-21: [06] 배치 크롤러 스케줄러 구현
```

---

## 다음 단계 (MVP)

| 단계 | 논문 수 | 벡터 수 (추정) | 목표 |
|------|---------|---------------|------|
| **테스트** | 100건 | ~2,000 | 파이프라인 검증 |
| **MVP** | 1만 건 | ~20만 | 챗봇 프로토타입 |
| **v1** | 10만 건 | ~200만 | 초기 서비스 |

---

## 참고 자료

- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [PMC Open Access Subset](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/)
- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
