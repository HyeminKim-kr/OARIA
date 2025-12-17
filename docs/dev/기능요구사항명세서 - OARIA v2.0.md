# Functional Requirements Specification

## OARIA
### Oncology AI Research Intelligence Assistant

# 기능 요구사항 명세서 (FRS)
**Detailed Functional Requirements Specification**

| 항목 | 내용 |
|------|------|
| 버전 | 2.0 |
| 작성일 | 2025. 12. 15 |
| 팀명 | OARIA |
| 팀원 | 김혜민 / 박영훈 / 윤태식 |
| 문서 유형 | Functional Requirements Specification (FRS) |

---

## 목차 (Table of Contents)

1. [문서 개요](#1-문서-개요)
2. [기능 요구사항 요약](#2-기능-요구사항-요약)
3. [핵심 기능 상세 (P0)](#3-핵심-기능-상세-p0)
   - F-01. Domain Classifier (도메인 분류기)
   - F-02. 암 논문 자동 batch 수집기
   - F-03. Evidence RAG 시스템
   - F-04. Agent Task 분해 시스템
   - F-05. Retrieval Confidence 검증
   - F-06. RAGAS 품질 평가 시스템
4. [부가 기능 상세 (P1/P2)](#4-부가-기능-상세-p1p2)
   - F-07. Frontend Dashboard
   - F-08. 논문 비교 분석
   - F-09. 유전자 트렌드 분석
5. [Multi-Gate Safety 시스템](#5-multi-gate-safety-시스템-종합)
6. [기능 의존성 매트릭스](#6-기능-의존성-매트릭스)

---

## 1. 문서 개요

### 1.1 목적

본 문서는 OARIA 시스템의 기능 요구사항을 상세히 정의합니다. 각 기능별로 입력/출력, 처리 로직, 예외 처리, 성공 기준, 테스트 케이스를 명시하여 개발 및 테스트의 기준을 제공합니다.

### 1.2 범위

- **핵심 기능 (P0)**: 6개 기능 - MVP 필수 구현
- **부가 기능 (P1)**: 2개 기능 - MVP 이후 구현
- **확장 기능 (P2)**: 1개 기능 - 향후 로드맵

### 1.3 우선순위 정의

| 우선순위 | 정의 | 설명 |
|----------|------|------|
| P0 | Must Have | MVP 출시를 위해 반드시 필요한 핵심 기능 |
| P1 | Should Have | MVP 이후 빠르게 추가해야 할 중요 기능 |
| P2 | Nice to Have | 있으면 좋지만 필수는 아닌 확장 기능 |

---

## 2. 기능 요구사항 요약

| ID | 기능명 | 설명 | 우선순위 | 담당 | Week |
|----|--------|------|----------|------|------|
| F-01 | Domain Classifier | 입력 쿼리의 의학 도메인 분류 (Gate 1) | P0 | 혜민 | W2-3 |
| F-02 | 암 논문 자동 batch 수집 | PubMed/PMC API 기반 논문 batch 크롤링 및 저장 | P0 | 영훈 | W1-2 |
| F-03 | Evidence RAG | PubMedBERT 임베딩 + Vector 검색 + 답변 생성 | P0 | 혜민 | W2-4 |
| F-04 | Agent Task 분해 | LangGraph 기반 복합 질문 분해 및 멀티스텝 추론 | P0 | 혜민 | W5-6 |
| F-05 | Retrieval Confidence | 검색 결과 유사도 기반 신뢰도 검증 (Gate 2) | P0 | 혜민 | W3-4 |
| F-06 | RAGAS 품질 평가 | Faithfulness, Relevancy 자동 평가 (Gate 3) | P0 | 혜민 | W4-5 |
| F-07 | FE Dashboard | Streamlit 기반 검색/분석 UI | P1 | 태식 | W6 |
| F-08 | 논문 비교 분석 | 두 논문의 방법론, 결과, 한계점 자동 비교 | P1 | 혜민 | W7+ |
| F-09 | 유전자 트렌드 | 유전자 언급 빈도 및 연구량 추세 시각화 | P2 | 영훈 | W7+ |

---

## 3. 핵심 기능 상세 (P0)

### F-01. Domain Classifier (도메인 분류기)

#### 3.1.1 기본 정보

| 항목 | 내용 |
|------|------|
| 기능 ID | F-01 |
| 기능명 | Domain Classifier (도메인 분류기) |
| 우선순위 | P0 (Must Have) |
| 담당자 | 김혜민 (AI Lead) |
| 예상 개발 기간 | Week 2-3 (1주) |
| 관련 Gate | Gate 1 - 진입 전 도메인 필터링 |

#### 3.1.2 기능 설명

사용자 입력 쿼리가 Oncology(암 연구) 도메인에 해당하는지 사전 분류하는 기능입니다. Multi-Gate 아키텍처의 첫 번째 방어선으로, Off-domain 쿼리가 RAG 파이프라인에 진입하는 것을 방지합니다.

**핵심 목적**: Cardiology, Neurology 등 다른 의학 도메인 질문이 잘못된 암 논문 기반으로 답변되는 것을 원천 차단

#### 3.1.3 입력/출력 명세

**입력 (Input)**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| query | string | 사용자 입력 질문 텍스트 (필수) |
| language | string | 입력 언어 (ko/en, 기본값: auto-detect) |

**출력 (Output)**

| 필드 | 타입 | 설명 |
|------|------|------|
| domain | string | 분류된 도메인 (oncology/cardiology/neurology/general_medicine/non_medical) |
| confidence | float | 분류 신뢰도 (0.0 ~ 1.0) |
| is_oncology | boolean | oncology 도메인 여부 |
| gate_passed | boolean | Gate 1 통과 여부 (confidence >= 0.8) |
| rejection_message | string \| null | 통과 실패 시 사용자 안내 메시지 |

#### 3.1.4 처리 로직

```python
def classify_domain(query: str) -> DomainResult:
    # 1. 텍스트 전처리
    cleaned_query = preprocess(query)

    # 2. PubMedBERT 임베딩 생성
    embedding = pubmedbert.encode(cleaned_query)

    # 3. Classification Head 통과
    logits = classifier_head(embedding)
    probabilities = softmax(logits)

    # 4. 최고 확률 도메인 선택
    domain = DOMAINS[argmax(probabilities)]
    confidence = max(probabilities)

    # 5. Gate 1 통과 여부 판정
    is_oncology = (domain == 'oncology')
    gate_passed = is_oncology and confidence >= 0.8

    # 6. 거절 메시지 생성 (필요시)
    rejection_message = None
    if not gate_passed:
        rejection_message = get_rejection_message(domain, confidence)

    return DomainResult(domain, confidence, is_oncology, gate_passed, rejection_message)
```

#### 3.1.5 분류 카테고리 및 거절 메시지

| 도메인 | 거절 메시지 템플릿 |
|--------|-------------------|
| oncology | (통과 - 메시지 없음) |
| cardiology | "저는 암 연구 전문 AI입니다. 심장 관련 질문은 심장내과 전문 리소스를 참고해 주세요." |
| neurology | "저는 암 연구 전문 AI입니다. 신경과 관련 질문은 해당 전문 리소스를 참고해 주세요." |
| general_medicine | "저는 암 연구에 특화된 AI입니다. 일반 의학 질문은 범용 의료 AI나 전문의와 상담해 주세요." |
| non_medical | "저는 암 연구 전문 AI입니다. 의학 외 질문에는 답변드리기 어렵습니다." |

#### 3.1.6 성공 기준 (Acceptance Criteria)

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | Oncology 쿼리 정확 분류율 | 테스트 데이터셋 | ≥ 95% |
| AC-2 | Off-domain 쿼리 차단율 | 테스트 데이터셋 | ≥ 98% |
| AC-3 | 분류 처리 시간 | API 응답 시간 | < 500ms |
| AC-4 | False Positive Rate (잘못된 통과) | 테스트 데이터셋 | < 2% |
| AC-5 | False Negative Rate (잘못된 차단) | 테스트 데이터셋 | < 5% |

#### 3.1.7 테스트 케이스

| TC# | 입력 | 예상 도메인 | 예상 결과 |
|-----|------|------------|----------|
| TC-1 | "EGFR 변이 폐암의 표적치료제는?" | oncology | PASS (conf ≥ 0.8) |
| TC-2 | "유방암 환자의 항암치료 부작용은?" | oncology | PASS |
| TC-3 | "심방세동의 치료법은?" | cardiology | REJECT |
| TC-4 | "파킨슨병 초기 증상은?" | neurology | REJECT |
| TC-5 | "오늘 날씨가 어때?" | non_medical | REJECT |
| TC-6 | "암 환자의 심장 합병증은?" | oncology | PASS (경계 케이스) |

#### 3.1.8 예외 처리

| 예외 상황 | 처리 방법 | 에러 코드 |
|----------|----------|----------|
| 빈 쿼리 입력 | 400 Bad Request 반환 | ERR_EMPTY_QUERY |
| 쿼리 길이 초과 (>1000자) | 쿼리 truncate 후 처리 | - |
| 모델 로딩 실패 | Fallback: 키워드 기반 분류 | ERR_MODEL_LOAD |
| 분류 신뢰도 < 0.5 | "ambiguous" 상태로 추가 확인 요청 | - |

---

### F-02. 암 논문 자동 batch 수집기

#### 3.2.1 기본 정보

| 항목 | 내용 |
|------|------|
| 기능 ID | F-02 |
| 기능명 | 암 논문 자동 batch 수집기 (Paper Crawler) |
| 우선순위 | P0 (Must Have) |
| 담당자 | 박영훈 (Data/Infra) |
| 예상 개발 기간 | Week 1-2 (2주) |
| 의존성 | PubMed API, PostgreSQL |

#### 3.2.2 기능 설명

PubMed/PMC API를 통해 암 관련 논문을 자동으로 batch 수집하고 메타데이터를 저장하는 기능입니다. 수집된 논문은 RAG 시스템의 지식 베이스가 됩니다.

#### 3.2.3 수집 대상 및 검색 쿼리

| 항목 | 설정 |
|------|------|
| 수집 소스 | PubMed (MEDLINE), PMC (PubMed Central) |
| 검색 쿼리 | `(cancer OR tumor OR oncology OR carcinoma OR neoplasm OR malignancy) AND (treatment OR therapy OR prognosis OR biomarker OR mutation)` |
| 필터: 언어 | English, Korean |
| 필터: 날짜 | 최근 5년 (초기 수집), 이후 Daily 증분 |
| 필터: 논문 유형 | Journal Article, Review, Clinical Trial, Meta-Analysis |
| 목표 수집량 | 초기 50,000건 → 최종 100,000건+ |

#### 3.2.4 입력/출력 명세

**입력 (Crawler 설정)**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| search_query | string | PubMed 검색 쿼리 |
| date_from | date | 수집 시작 날짜 |
| date_to | date | 수집 종료 날짜 |
| max_results | int | 최대 수집 건수 (기본: 10000) |
| batch_size | int | API 호출당 건수 (기본: 200) |

**출력 (저장 데이터)**

| 필드 | 타입 | 설명 |
|------|------|------|
| pmid | string | PubMed ID (Primary Key) |
| title | string | 논문 제목 |
| abstract | text | 초록 전문 |
| authors | json[] | 저자 목록 [{name, affiliation}] |
| journal | string | 저널명 |
| pub_date | date | 출판일 |
| mesh_terms | string[] | MeSH 키워드 |
| keywords | string[] | 저자 키워드 |
| doi | string | DOI |
| pmc_id | string | PMC ID (있는 경우) |
| full_text_url | string | 전문 링크 (Open Access) |

#### 3.2.5 처리 로직

```python
async def crawl_papers(config: CrawlerConfig) -> CrawlResult:
    # 1. PubMed API 검색
    search_result = pubmed_api.search(
        query=config.search_query,
        mindate=config.date_from,
        maxdate=config.date_to,
        retmax=config.max_results
    )
    pmid_list = search_result.id_list

    # 2. 배치 단위로 상세 정보 수집
    papers = []
    for batch in chunk(pmid_list, config.batch_size):
        details = pubmed_api.fetch(batch)
        papers.extend(parse_papers(details))
        await rate_limit_delay()  # API 제한 준수

    # 3. 중복 제거 및 DB 저장
    new_papers = filter_existing(papers)
    saved_count = db.bulk_insert(new_papers)

    # 4. 임베딩 생성 트리거
    await trigger_embedding_job(new_papers)

    return CrawlResult(total=len(pmid_list), saved=saved_count)
```

#### 3.2.6 성공 기준

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 초기 수집 완료 | DB 카운트 | ≥ 50,000건 |
| AC-2 | 메타데이터 완성도 | 필수 필드 null 비율 | < 5% |
| AC-3 | 수집 성공률 | (성공/시도) 비율 | ≥ 98% |
| AC-4 | 중복 방지 | 중복 PMID 검출 | 0건 |
| AC-5 | API 제한 준수 | 429 에러 발생 횟수 | 0회/일 |

#### 3.2.7 예외 처리

| 예외 상황 | 처리 방법 | 재시도 |
|----------|----------|--------|
| API Rate Limit (429) | Exponential backoff: 1s → 2s → 4s → 8s | 최대 5회 |
| 네트워크 타임아웃 | 해당 배치 재시도 후 스킵 | 최대 3회 |
| 파싱 실패 | 로그 기록 후 해당 논문 스킵 | - |
| DB 연결 실패 | 메모리 버퍼링 후 재연결 시도 | 무한 |

---

### F-03. Evidence RAG 시스템

#### 3.3.1 기본 정보

| 항목 | 내용 |
|------|------|
| 기능 ID | F-03 |
| 기능명 | Evidence RAG (검색 증강 생성) 시스템 |
| 우선순위 | P0 (Must Have) |
| 담당자 | 김혜민 (AI Lead) |
| 예상 개발 기간 | Week 2-4 (3주) |
| 의존성 | F-02 (논문 수집), PubMedBERT, ChromaDB/Qdrant |

#### 3.3.2 기능 설명

사용자 질문에 대해 관련 논문을 검색하고, 검색된 논문을 근거로 답변을 생성하는 핵심 RAG 시스템입니다. 모든 답변에는 인용 논문 정보가 포함됩니다.

#### 3.3.3 서브 컴포넌트

| 컴포넌트 | 설명 |
|----------|------|
| Chunker | 논문 텍스트를 512토큰 단위로 분할, 50토큰 오버랩 |
| Embedder | PubMedBERT로 청크별 768차원 벡터 생성 |
| Vector Store | ChromaDB/Qdrant에 벡터 저장 및 인덱싱 |
| Retriever | 쿼리 임베딩 → Top-k 유사 청크 검색 |
| Reranker | Cross-encoder로 검색 결과 재순위화 |
| Generator | LLM이 컨텍스트 기반 답변 생성 |
| Citation Linker | 답변에 논문 인용 정보 매핑 |

#### 3.3.4 입력/출력 명세

**입력**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| query | string | 사용자 질문 (Gate 1 통과 후) |
| top_k | int | 검색할 문서 수 (기본: 10) |
| rerank_top_n | int | Rerank 후 사용할 문서 수 (기본: 5) |
| include_abstract | bool | 초록 전문 포함 여부 (기본: true) |

**출력**

| 필드 | 타입 | 설명 |
|------|------|------|
| answer | string | 생성된 답변 텍스트 |
| evidence | Evidence[] | 인용 논문 목록 |
| evidence[].pmid | string | 논문 PubMed ID |
| evidence[].title | string | 논문 제목 |
| evidence[].relevance_score | float | 관련성 점수 (0-1) |
| evidence[].snippet | string | 인용된 텍스트 조각 |
| retrieval_scores | float[] | 각 문서의 유사도 점수 |
| processing_time_ms | int | 처리 시간 (밀리초) |

#### 3.3.5 RAG 파이프라인 흐름

```python
async def evidence_rag(query: str, config: RAGConfig) -> RAGResult:
    # 1. 쿼리 임베딩 생성
    query_embedding = pubmedbert.encode(query)

    # 2. Vector DB 검색 (Top-k)
    candidates = vector_db.search(query_embedding, top_k=config.top_k)

    # 3. Reranking (Cross-encoder)
    reranked = reranker.rerank(query, candidates, top_n=config.rerank_top_n)

    # 4. 컨텍스트 구성
    context = build_context(reranked, include_abstract=config.include_abstract)

    # 5. LLM 답변 생성
    prompt = build_prompt(query, context)
    answer = await llm.generate(prompt)

    # 6. 인용 정보 매핑
    evidence = map_citations(answer, reranked)

    return RAGResult(answer=answer, evidence=evidence, retrieval_scores=[...])
```

#### 3.3.6 프롬프트 템플릿

```python
SYSTEM_PROMPT = '''
당신은 암 연구 전문 AI 어시스턴트입니다.
아래 제공된 논문 정보만을 근거로 질문에 답변하세요.

규칙:
1. 제공된 논문에 없는 내용은 답변하지 마세요.
2. 각 주장에 [PMID:숫자] 형식으로 출처를 표기하세요.
3. 불확실한 내용은 "~로 알려져 있습니다" 등으로 표현하세요.
4. 임상적 결정을 직접 권유하지 마세요.
'''

USER_PROMPT = '''
## 참고 논문
{context}

## 질문
{query}

위 논문들을 참고하여 질문에 답변해 주세요.
'''
```

#### 3.3.7 성공 기준

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 검색 관련성 (Retrieval Precision@5) | 수동 평가 | ≥ 80% |
| AC-2 | 답변 인용 정확도 | PMID 검증 | 100% |
| AC-3 | 단순 쿼리 응답 시간 | API 측정 | < 3초 |
| AC-4 | 복합 쿼리 응답 시간 | API 측정 | < 10초 |
| AC-5 | 답변에 인용 포함 비율 | 자동 검사 | 100% |

---

### F-04. Agent Task 분해 시스템

#### 3.4.1 기본 정보

| 항목 | 내용 |
|------|------|
| 기능 ID | F-04 |
| 기능명 | Agent Task 분해 시스템 (LangGraph Agent) |
| 우선순위 | P0 (Must Have) |
| 담당자 | 김혜민 (AI Lead) |
| 예상 개발 기간 | Week 5-6 (2주) |
| 의존성 | F-03 (Evidence RAG), LangGraph |

#### 3.4.2 기능 설명

복잡한 사용자 질문을 분석하여 여러 하위 태스크로 분해하고, 각 태스크를 순차적/병렬적으로 처리한 후 결과를 종합하는 Agentic 시스템입니다.

#### 3.4.3 쿼리 복잡도 분류

| 복잡도 | 정의 | 예시 |
|--------|------|------|
| Simple | 단일 개념, 직접 검색 | "EGFR이란 무엇인가?" |
| Medium | 2-3개 개념 조합 | "EGFR 변이 폐암의 표적치료제는?" |
| Complex | 다중 조건, 비교, 추론 | "EGFR+TP53 이중 변이 환자의 1차 치료 vs 2차 치료 효과 비교" |

#### 3.4.4 Agent 노드 구성

| 노드 | 역할 |
|------|------|
| Complexity Analyzer | 쿼리 복잡도 분석 (Simple/Medium/Complex) |
| Task Decomposer | 복잡 쿼리를 하위 태스크로 분해 |
| Tool Router | 각 태스크에 적합한 도구 선택 (RAG, Compare, Trend 등) |
| Executor | 선택된 도구로 태스크 실행 |
| Evidence Synthesizer | 여러 태스크 결과를 종합하여 최종 답변 생성 |

#### 3.4.5 LangGraph State 정의

```python
class AgentState(TypedDict):
    query: str                    # 원본 질문
    complexity: str               # simple/medium/complex
    sub_tasks: List[SubTask]      # 분해된 하위 태스크
    task_results: List[TaskResult] # 각 태스크 실행 결과
    context: List[Document]       # 수집된 컨텍스트
    final_answer: str             # 최종 답변
    evidence: List[Evidence]      # 인용 논문
    gate_status: GateStatus       # 각 Gate 통과 상태
```

#### 3.4.6 Task 분해 예시

**입력**: "EGFR 과발현 + TP53 결손 환자의 폐암에서 면역항암제 vs 표적치료제 효과 비교"

**분해 결과**:
```
├── SubTask 1: "EGFR 과발현 폐암의 특성" (RAG)
├── SubTask 2: "TP53 결손이 폐암에 미치는 영향" (RAG)
├── SubTask 3: "EGFR+TP53 이중 변이의 임상적 의미" (RAG)
├── SubTask 4: "면역항암제 치료 효과" (RAG)
├── SubTask 5: "표적치료제 치료 효과" (RAG)
└── SubTask 6: "두 치료법 비교 분석" (Compare Tool)
```

#### 3.4.7 성공 기준

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 복잡도 분류 정확도 | 테스트 데이터셋 | ≥ 90% |
| AC-2 | Task 분해 적절성 | 수동 평가 | ≥ 85% |
| AC-3 | Complex 쿼리 처리 시간 | API 측정 | < 15초 |
| AC-4 | 결과 종합 품질 | RAGAS 평가 | ≥ 0.80 |

---

### F-05. Retrieval Confidence 검증 (Gate 2)

#### 3.5.1 기본 정보

| 항목 | 내용 |
|------|------|
| 기능 ID | F-05 |
| 기능명 | Retrieval Confidence 검증 (Gate 2) |
| 우선순위 | P0 (Must Have) |
| 담당자 | 김혜민 (AI Lead) |
| 관련 Gate | Gate 2 - 검색 결과 신뢰도 검증 |

#### 3.5.2 기능 설명

RAG 검색 결과의 품질을 검증하는 두 번째 Gate입니다. 검색된 문서들이 실제로 쿼리와 관련이 있는지, 그리고 oncology 도메인에 해당하는지를 확인합니다.

#### 3.5.3 검증 항목

| 검증 항목 | 기준 | 실패 시 동작 |
|----------|------|-------------|
| Similarity Threshold | max(similarity) ≥ 0.7 | "관련 정보 부족" 메시지 |
| Min Relevant Docs | similarity ≥ 0.6인 문서 ≥ 3개 | "충분한 근거 없음" 메시지 |
| Domain Validation | oncology 문서 비율 ≥ 80% | "도메인 불일치" 경고 |

#### 3.5.4 처리 로직

```python
def gate2_retrieval_confidence(query: str, docs: List[Document]) -> Gate2Result:
    # 1. Similarity 점수 확인
    max_sim = max(d.similarity for d in docs)
    if max_sim < 0.7:
        return Gate2Result(
            passed=False,
            reason='low_similarity',
            message='관련 논문을 충분히 찾지 못했습니다. 질문을 더 구체적으로 해주세요.'
        )

    # 2. 관련 문서 수 확인
    relevant_count = sum(1 for d in docs if d.similarity >= 0.6)
    if relevant_count < 3:
        return Gate2Result(
            passed=False,
            reason='insufficient_docs',
            message='충분한 근거 논문을 찾지 못했습니다.'
        )

    # 3. 도메인 검증
    oncology_ratio = sum(1 for d in docs if is_oncology_doc(d)) / len(docs)
    if oncology_ratio < 0.8:
        return Gate2Result(
            passed=False,
            reason='domain_mismatch',
            message='검색 결과가 암 연구와 관련성이 낮습니다.'
        )

    return Gate2Result(passed=True, max_similarity=max_sim, relevant_count=relevant_count)
```

#### 3.5.5 성공 기준

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 저품질 검색 결과 차단율 | 테스트셋 | ≥ 95% |
| AC-2 | 고품질 결과 오차단율 (False Negative) | 테스트셋 | < 3% |
| AC-3 | Off-domain 문서 감지율 | 테스트셋 | ≥ 90% |

---

### F-06. RAGAS 품질 평가 시스템 (Gate 3)

#### 3.6.1 기본 정보

| 항목 | 내용 |
|------|------|
| 기능 ID | F-06 |
| 기능명 | RAGAS 품질 평가 시스템 (Gate 3) |
| 우선순위 | P0 (Must Have) |
| 담당자 | 김혜민 (AI Lead) |
| 예상 개발 기간 | Week 4-5 (2주) |
| 관련 Gate | Gate 3 - 최종 답변 품질 검증 |

#### 3.6.2 기능 설명

생성된 답변의 품질을 RAGAS 프레임워크로 자동 평가하는 마지막 Gate입니다. Faithfulness(사실성), Answer Relevancy(답변 관련성), Context Precision(컨텍스트 정밀도) 등을 측정합니다.

#### 3.6.3 평가 메트릭 상세

| 메트릭 | 정의 | 임계값 |
|--------|------|--------|
| Faithfulness | 답변의 모든 주장이 검색된 컨텍스트에 근거하는 비율 | ≥ 0.85 |
| Answer Relevancy | 답변이 원래 질문에 얼마나 관련있는지 | ≥ 0.80 |
| Context Precision | 검색된 컨텍스트 중 실제로 유용한 비율 | ≥ 0.70 |
| Context Recall | 정답에 필요한 정보가 컨텍스트에 포함된 비율 | ≥ 0.70 |

#### 3.6.4 처리 로직

```python
async def gate3_ragas_evaluation(
    query: str, context: List[str], answer: str
) -> Gate3Result:
    # 1. RAGAS 평가 실행
    scores = await ragas.evaluate(
        queries=[query],
        contexts=[context],
        answers=[answer],
        metrics=['faithfulness', 'answer_relevancy', 'context_precision']
    )

    # 2. 임계값 검사
    faithfulness = scores['faithfulness'][0]
    relevancy = scores['answer_relevancy'][0]

    if faithfulness < 0.85 or relevancy < 0.80:
        return Gate3Result(
            passed=False,
            status='low_confidence',
            scores=scores,
            warning='이 답변은 신뢰도가 낮습니다. 추가 검증을 권장합니다.'
        )

    return Gate3Result(passed=True, scores=scores)
```

#### 3.6.5 Gate 3 통과/실패 시 동작

| 상태 | 동작 |
|------|------|
| PASS | 정상 답변 반환 + 품질 점수 표시 |
| LOW_CONFIDENCE | 답변 반환 + 경고 메시지 + 점수 표시: "[신뢰도 주의] 이 답변의 Faithfulness: 0.72..." |
| FAIL | 답변 반환 거부 + 재질문 요청: "신뢰할 수 있는 답변을 생성하지 못했습니다..." |

#### 3.6.6 성공 기준

| AC# | 기준 | 측정 방법 | 목표치 |
|-----|------|----------|--------|
| AC-1 | 평균 Faithfulness 점수 | 1000개 쿼리 평가 | ≥ 0.85 |
| AC-2 | 평균 Answer Relevancy 점수 | 1000개 쿼리 평가 | ≥ 0.80 |
| AC-3 | 저품질 답변 차단율 | 수동 검증 | ≥ 90% |
| AC-4 | 평가 처리 시간 | API 측정 | < 2초 |

---

## 4. 부가 기능 상세 (P1/P2)

### F-07. Frontend Dashboard

| 항목 | 내용 |
|------|------|
| 기능 ID | F-07 |
| 우선순위 | P1 (Should Have) |
| 담당자 | 윤태식 (Backend Lead) |
| 기술 스택 | Streamlit (MVP) → Next.js (확장) |

**주요 화면**:
- **메인 검색 화면**: 질문 입력, 최신 논문 트렌드
- **결과 화면**: AI 답변 + 인용 논문 + RAGAS 점수 + Gate 상태
- **논문 상세**: 메타데이터, Abstract, 관련 Entity 하이라이트
- **히스토리**: 과거 질문/답변 기록

---

### F-08. 논문 비교 분석

| 항목 | 내용 |
|------|------|
| 기능 ID | F-08 |
| 우선순위 | P1 (Should Have) |
| 담당자 | 김혜민 (AI Lead) |

**기능**: 두 논문 또는 치료법의 방법론, 결과, 한계점을 자동으로 비교 분석

**입력**: 두 개의 PMID 또는 비교 질문

**출력**: Side-by-side 비교표 + 종합 분석

---

### F-09. 유전자 트렌드 분석

| 항목 | 내용 |
|------|------|
| 기능 ID | F-09 |
| 우선순위 | P2 (Nice to Have) |
| 담당자 | 박영훈 (Data/Infra) |

**기능**: 특정 유전자의 논문 언급 빈도, 연구량 증가 추세 시각화

**입력**: 유전자 심볼 (예: EGFR, TP53, BRCA1)

**출력**: 연도별 논문 수 차트, 관련 치료제/질환 워드클라우드

---

## 5. Multi-Gate Safety 시스템 종합

OARIA의 핵심 안전장치인 3-Gate 시스템을 종합적으로 정리합니다.

### 5.1 Gate 시스템 요약

| Gate | 기능 | 통과 조건 | 관련 기능 | 실패 동작 |
|------|------|----------|----------|----------|
| Gate 1 | Domain Classifier | oncology conf ≥ 0.8 | F-01 | Reject |
| Gate 2 | Retrieval Confidence | similarity ≥ 0.7 | F-05 | Insufficient |
| Gate 3 | RAGAS Quality | Faith ≥ 0.85, Rel ≥ 0.80 | F-06 | Low Conf |

### 5.2 전체 흐름도

```
User Query
    │
    ▼
┌─────────────────┐     ❌ Reject
│   GATE 1        │────────────────→ "저는 암 연구 전문 AI입니다..."
│ Domain Classify │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│   RAG Pipeline  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ❌ Insufficient
│   GATE 2        │────────────────→ "관련 정보를 찾지 못했습니다..."
│ Retrieval Conf  │
└────────┬────────┘
         │ ✅
         ▼
┌─────────────────┐
│   LLM Generate  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ⚠️ Low Confidence
│   GATE 3        │────────────────→ "[주의] 신뢰도 낮음..." + 점수
│ RAGAS Evaluate  │
└────────┬────────┘
         │ ✅
         ▼
   ✅ Final Answer + Evidence + Scores
```

---

## 6. 기능 의존성 매트릭스

| 기능 | F-01 | F-02 | F-03 | F-04 | F-05 | F-06 | F-07 | F-08 |
|------|------|------|------|------|------|------|------|------|
| F-01 Domain | - | | | | | | | |
| F-02 Crawler | | - | | | | | | |
| F-03 RAG | ● | ● | - | | | | | |
| F-04 Agent | ● | | ● | - | | | | |
| F-05 RetConf | | | ● | | - | | | |
| F-06 RAGAS | | | ● | | ● | - | | |
| F-07 FE | ● | | ● | ● | ● | ● | - | |
| F-08 Compare | | ● | ● | ● | | ● | | - |

**● = 의존성 있음** (해당 기능 완료 후 개발 가능)

### 6.1 개발 순서 권장

```
Week 1-2: F-02 (Crawler) ─────────────────────────────────┐
                                                          │
Week 2-3: F-01 (Domain Classifier) ──────────┐            │
                                              │            │
Week 2-4: F-03 (Evidence RAG) ←──────────────┴────────────┘
                   │
Week 3-4: F-05 (Retrieval Confidence) ←──────┘
                   │
Week 4-5: F-06 (RAGAS) ←──────────────────────┘
                   │
Week 5-6: F-04 (Agent) ←─────────────────────┘
                   │
Week 6:   F-07 (FE Dashboard)
```

---

*- End of Document -*
