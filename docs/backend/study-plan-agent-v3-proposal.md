# Study Plan Agent v3 - 자율성 강화 제안서

> **Date**: 2025-01-21
> **Status**: Draft (피드백 대기)
> **Author**: Claude

---

## 1. 현재 상태 분석 (v2.1)

### 1.1 구현된 것

```
입력 → [13개 노드 순차 실행] → 출력
         ↑
     3개 조건부 루프
```

| 구성요소 | 설명 | 상태 |
|----------|------|------|
| 13개 노드 | parse → clarify → decompose → search → ... → synthesize | ✅ 완료 |
| Loop 0 | 가설 명확화 (confidence < 0.7 → clarify) | ✅ 완료 |
| Loop 1 | 검색 확장 (coverage < 0.6 → expand, 최대 2회) | ✅ 완료 |
| Loop 2 | 실험 재설계 (quality < 0.8 → redesign, 최대 2회) | ✅ 완료 |
| RAG 연동 | 기존 rag_service 활용한 논문 검색 | ✅ 완료 |
| SSE 스트리밍 | 실시간 진행 상태 전송 | ✅ 완료 |
| DB 저장 | study_plans 테이블 저장 | ✅ 완료 |

### 1.2 현재 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Study Plan Agent v2.1                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│  │ Node 1  │───▶│ Node 2  │───▶│ Node 3  │───▶│ Node 4  │───▶ ...     │
│  │ (parse) │    │(clarify)│    │(decomp) │    │(search) │              │
│  └─────────┘    └────┬────┘    └─────────┘    └────┬────┘              │
│       ▲              │                              │                   │
│       │              │ confidence                   │ coverage          │
│       └──────────────┘ < 0.7                        │ < 0.6             │
│                                                     ▼                   │
│                                               ┌─────────┐              │
│                                               │ expand  │              │
│                                               └─────────┘              │
│                                                                         │
│  특징:                                                                  │
│  - 노드 순서가 고정됨 (Deterministic Flow)                              │
│  - 분기 조건이 하드코딩됨 (0.7, 0.6, 0.8 등)                            │
│  - LLM은 "점수 매기기"만 담당                                           │
│  - 다음 행동을 LLM이 선택하지 않음                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 에이전트 자율성 평가

| 평가 항목 | 설명 | 현재 수준 |
|-----------|------|-----------|
| **Task Decomposition** | 목표를 하위 작업으로 분해 | ⚠️ 30% - 고정된 13단계 |
| **Tool Selection** | 상황에 맞는 도구 선택 | ❌ 0% - RAG만 고정 사용 |
| **Dynamic Planning** | 실행 중 계획 수정 | ❌ 0% - 계획 수정 없음 |
| **Self-Reflection** | 결과 평가 및 전략 수정 | ⚠️ 40% - 점수 기반 루프만 |
| **Goal-Driven Behavior** | 목표 달성까지 자율 행동 | ⚠️ 30% - 최대 반복 후 포기 |

**종합 평가**: 현재는 **"LLM-augmented Workflow"** 수준이며, **"Autonomous Agent"** 라고 하기엔 부족

---

## 2. 개선 목표

### 2.1 진짜 에이전트란?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Autonomous Agent                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │                      Agent Core (LLM)                         │     │
│   │                                                               │     │
│   │   1. 현재 상태 관찰 (Observe)                                 │     │
│   │   2. 다음 행동 결정 (Think/Plan)                              │     │
│   │   3. 도구 실행 (Act)                                          │     │
│   │   4. 결과 평가 (Reflect)                                      │     │
│   │   5. 목표 달성? → 종료 / 미달성? → 1로 돌아감                  │     │
│   │                                                               │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │                      Tool Registry                            │     │
│   │                                                               │     │
│   │   - search_papers: 논문 검색                                  │     │
│   │   - analyze_paper: 특정 논문 심층 분석                        │     │
│   │   - design_experiment: 실험 설계                              │     │
│   │   - validate_design: 설계 검증                                │     │
│   │   - ask_user: 사용자에게 질문                                 │     │
│   │   - finish: 작업 완료                                         │     │
│   │                                                               │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 차이점

| 현재 (v2.1) | 목표 (v3) |
|-------------|-----------|
| 노드 순서 고정 | LLM이 매번 다음 행동 결정 |
| 분기 조건 하드코딩 | LLM이 상황 판단하여 분기 |
| RAG만 사용 | 다양한 Tool 중 선택 |
| 최대 2회 반복 후 포기 | 목표 달성까지 전략 수정 |
| 에러 시 그냥 진행 | 에러 원인 분석 후 대안 시도 |

---

## 3. 제안하는 아키텍처 (v3)

### 3.1 Option A: ReAct 패턴

**개념**: Reasoning + Acting을 번갈아 수행

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ReAct Agent Loop                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   User Input: "MET amplification이 osimertinib 내성을 유발한다"         │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Iteration 1                                                  │      │
│   │                                                              │      │
│   │ Thought: 이 가설을 검증하려면 먼저 기존 연구를 찾아봐야 해.   │      │
│   │          MET과 osimertinib 관련 논문을 검색하자.             │      │
│   │                                                              │      │
│   │ Action: search_papers("MET amplification osimertinib         │      │
│   │         resistance EGFR")                                    │      │
│   │                                                              │      │
│   │ Observation: 12개 논문 발견. 주요 발견:                       │      │
│   │   - PMID:12345: MET bypass가 주요 내성 기전                  │      │
│   │   - PMID:23456: MET inhibitor 병용 효과 연구                 │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Iteration 2                                                  │      │
│   │                                                              │      │
│   │ Thought: 논문들이 있네. PMID:12345를 더 자세히 분석해서       │      │
│   │          어떤 실험 방법을 썼는지 확인해야겠다.                │      │
│   │                                                              │      │
│   │ Action: analyze_paper("PMID:12345", focus="methodology")     │      │
│   │                                                              │      │
│   │ Observation: Cell viability assay (MTT), Western blot for    │      │
│   │   MET phosphorylation, IC50 measurement...                   │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Iteration 3                                                  │      │
│   │                                                              │      │
│   │ Thought: 방법론을 파악했다. 이제 실험을 설계할 수 있겠다.     │      │
│   │          선행연구의 방법론을 참고해서 설계하자.               │      │
│   │                                                              │      │
│   │ Action: design_experiment(                                   │      │
│   │   hypothesis="MET amp causes osimertinib resistance",        │      │
│   │   reference_methods=["MTT assay", "Western blot"],           │      │
│   │   experiment_type="in_vitro"                                 │      │
│   │ )                                                            │      │
│   │                                                              │      │
│   │ Observation: 실험 설계 초안 생성됨                           │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│                            ...                                          │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Iteration N                                                  │      │
│   │                                                              │      │
│   │ Thought: 실험 설계가 완성됐고 품질 검증도 통과했다.          │      │
│   │          이제 최종 계획서를 생성하면 된다.                    │      │
│   │                                                              │      │
│   │ Action: finish(plan=generated_plan)                          │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**장점**:
- 완전한 자율성 - LLM이 모든 판단
- 유연한 실행 경로 - 상황에 맞게 적응
- 명시적 추론 과정 - 디버깅 용이

**단점**:
- 토큰 사용량 증가 (매번 전체 맥락 전달)
- 무한 루프 위험 (잘못된 판단 반복)
- 예측 불가능한 실행 시간

---

### 3.2 Option B: Plan-and-Execute 패턴

**개념**: 먼저 계획을 세우고, 계획대로 실행. 필요시 계획 수정.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Plan-and-Execute Agent                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Phase 1: Planning                                            │      │
│   │                                                              │      │
│   │ Input: "MET amplification이 osimertinib 내성을 유발한다"     │      │
│   │                                                              │      │
│   │ Generated Plan:                                              │      │
│   │   Step 1: 가설 구조화 (독립/종속 변수 추출)                  │      │
│   │   Step 2: 선행연구 검색 (MET, osimertinib, resistance)       │      │
│   │   Step 3: 방법론 분석 (어떤 실험 방법이 주로 사용되는지)     │      │
│   │   Step 4: 실험 설계 (in_vitro 우선)                          │      │
│   │   Step 5: 설계 검증                                          │      │
│   │   Step 6: 측정치 식별                                        │      │
│   │   Step 7: 최종 계획서 생성                                   │      │
│   │                                                              │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Phase 2: Execution                                           │      │
│   │                                                              │      │
│   │ Executing Step 1: 가설 구조화                                │      │
│   │   → Result: IV=MET amp, DV=osimertinib resistance            │      │
│   │   → Status: ✅ Success                                       │      │
│   │                                                              │      │
│   │ Executing Step 2: 선행연구 검색                              │      │
│   │   → Result: 3개 논문만 발견 (부족)                           │      │
│   │   → Status: ⚠️ Partial - 계획 수정 필요                      │      │
│   │                                                              │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Phase 3: Re-Planning (필요시)                                │      │
│   │                                                              │      │
│   │ 문제: Step 2에서 논문이 부족함                               │      │
│   │                                                              │      │
│   │ Updated Plan:                                                │      │
│   │   Step 2-1: 검색어 확장 (동의어 추가)                        │      │
│   │   Step 2-2: 재검색                                           │      │
│   │   Step 3: 방법론 분석 (계속)                                 │      │
│   │   ...                                                        │      │
│   │                                                              │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│                     Continue Execution...                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**장점**:
- 예측 가능한 실행 흐름
- 사용자에게 계획 미리 공유 가능
- 토큰 효율적 (계획 단계에서만 많이 사용)

**단점**:
- Re-planning 로직 복잡
- 초기 계획이 잘못되면 전체 영향

---

### 3.3 Option C: 하이브리드 (현재 + 동적 판단 추가)

**개념**: 기존 파이프라인 유지 + 주요 분기점에서 LLM 동적 판단

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Hybrid Agent (v3)                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   기존 파이프라인 (골격 유지)                                           │
│   ─────────────────────────────                                         │
│                                                                         │
│   parse → decompose → search → build_evidence → design → ...           │
│                                                                         │
│   BUT! 주요 분기점에서 LLM 동적 판단 추가                               │
│   ─────────────────────────────────────────                             │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Decision Point 1: After Search                              │      │
│   │                                                              │      │
│   │ LLM Prompt:                                                  │      │
│   │   "검색 결과: 5개 논문, 커버리지 0.4                         │      │
│   │    다음 중 어떤 행동이 적절한가?                             │      │
│   │    A) 검색어 확장 후 재검색                                  │      │
│   │    B) 다른 DB 검색 (PubMed API 직접 호출)                    │      │
│   │    C) 현재 결과로 진행 (충분함)                              │      │
│   │    D) 사용자에게 추가 키워드 요청"                           │      │
│   │                                                              │      │
│   │ LLM Response: "A - 검색어에 동의어 추가 필요"                │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │ Decision Point 2: After Critique                            │      │
│   │                                                              │      │
│   │ LLM Prompt:                                                  │      │
│   │   "품질 점수: 0.65, 문제: control group 부족                 │      │
│   │    다음 중 어떤 행동이 적절한가?                             │      │
│   │    A) 실험 재설계 (control 추가)                             │      │
│   │    B) 추가 선행연구 검색 (control 설계 참고용)               │      │
│   │    C) 사용자에게 어떤 control이 필요한지 질문                │      │
│   │    D) 현재 상태로 진행 (minor issue)"                        │      │
│   │                                                              │      │
│   │ LLM Response: "B - 유사 연구의 control 설계 참고 필요"       │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**장점**:
- 기존 코드 대부분 재사용
- 점진적 개선 가능
- 예측 가능성 유지하면서 유연성 추가

**단점**:
- "진짜" 에이전트에 비해 자율성 제한적
- Decision Point 설계 필요

---

## 4. 도구(Tool) 정의

어떤 옵션을 선택하든 에이전트가 사용할 수 있는 도구 정의가 필요합니다.

### 4.1 검색 도구: 다중 소스 전략

**핵심 아이디어**: 단일 RAG 의존 → 다중 소스 검색으로 확장

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Multi-Source Search Strategy                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Agent가 검색 필요시 → LLM이 적절한 소스 선택                          │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │                    Search Tools                              │      │
│   ├─────────────────────────────────────────────────────────────┤      │
│   │                                                              │      │
│   │  1. search_rag (내부 DB)                                     │      │
│   │     └─ Weaviate 벡터 검색                                    │      │
│   │     └─ 이미 수집된 논문 full-text 검색                       │      │
│   │     └─ 빠름, 스니펫 포함                                     │      │
│   │                                                              │      │
│   │  2. search_europe_pmc (Europe PMC API)                       │      │
│   │     └─ Open Access 논문 검색                                 │      │
│   │     └─ Full-text 접근 가능                                   │      │
│   │     └─ 최신 논문 커버리지 좋음                               │      │
│   │                                                              │      │
│   │  3. search_google_scholar (Google Scholar)                   │      │
│   │     └─ 가장 넓은 커버리지                                    │      │
│   │     └─ 인용수 정보 포함                                      │      │
│   │     └─ Rate limit 주의                                       │      │
│   │                                                              │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
│   사용 시나리오:                                                        │
│   ─────────────────                                                     │
│   1. 기본 검색 → search_rag (빠르고 스니펫 있음)                        │
│   2. RAG 결과 부족 → search_europe_pmc (Open Access 확장)               │
│   3. 여전히 부족 → search_google_scholar (최대 커버리지)                │
│   4. 특정 논문 상세 → search_europe_pmc (full-text 가져오기)            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 4.1.1 최종 검색 스택 (확정)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    검색 Tool 스택 (3-tier)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1차: search_rag (내부 Weaviate)                                        │
│       └─ 비용: 무료                                                     │
│       └─ 용도: 수집된 논문 full-text 벡터 검색                          │
│       └─ 장점: 빠름, 스니펫 포함                                        │
│                                                                         │
│  2차: search_europe_pmc (Europe PMC API)                                │
│       └─ 비용: 무료, 무제한                                             │
│       └─ 용도: Open Access 논문 검색 + Full-text 추출                   │
│       └─ 장점: 최신 OA 논문, 인용/참조 관계                             │
│                                                                         │
│  3차: search_web (Tavily API)                                           │
│       └─ 비용: 월 1,000회 무료                                          │
│       └─ 용도: 일반 웹 검색 (프로토콜, 가이드라인, 최신 정보)           │
│       └─ 장점: LangChain 통합 쉬움, 검색+요약 통합                      │
│       └─ 제한: 무료 한도 내에서만 사용 (exceeded 시 skip)               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 4.1.2 각 소스별 특성 비교

| 소스 | 비용 | 장점 | 단점 | 용도 |
|------|------|------|------|------|
| **RAG (Weaviate)** | 무료 | 빠름, 스니펫 포함 | 수집된 논문만 | 1차 검색, 방법론 분석 |
| **Europe PMC** | 무료 | Full-text, 인용관계 | OA 논문만 | 2차 확장, 상세 분석 |
| **Tavily** | 월 1,000회 무료 | 웹 전체, 요약 포함 | 한도 초과시 불가 | 최신 정보, 프로토콜 |

#### 4.1.2 Europe PMC API 상세

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Europe PMC API                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Base URL: https://www.ebi.ac.uk/europepmc/webservices/rest             │
│                                                                         │
│  주요 Endpoints:                                                        │
│  ──────────────                                                         │
│                                                                         │
│  1. /search                                                             │
│     GET /search?query={query}&resultType=core&format=json               │
│     → 논문 메타데이터 + abstract 검색                                   │
│                                                                         │
│  2. /article/{source}/{id}/fullTextXML                                  │
│     GET /article/PMC/PMC1234567/fullTextXML                             │
│     → Open Access 논문 Full-text (XML)                                  │
│                                                                         │
│  3. /article/{source}/{id}/references                                   │
│     → 해당 논문의 참조 문헌 목록                                        │
│                                                                         │
│  4. /article/{source}/{id}/citations                                    │
│     → 해당 논문을 인용한 논문 목록                                      │
│                                                                         │
│  Query 문법 예시:                                                       │
│  ────────────────                                                       │
│  - 기본: "EGFR mutation resistance"                                     │
│  - 필드 지정: TITLE:"osimertinib resistance"                            │
│  - 연도 필터: (PUB_YEAR:[2020 TO 2024])                                 │
│  - Open Access만: (OPEN_ACCESS:y)                                       │
│  - 복합: (TITLE:"MET amplification") AND (ABSTRACT:"EGFR")              │
│                                                                         │
│  Rate Limit: 없음 (but 과도한 요청 시 차단 가능)                        │
│  인증: 불필요 (public API)                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 4.1.3 검색 Tool 정의

```python
# Tool 1: 내부 RAG 검색
search_rag = {
    "name": "search_rag",
    "description": """
        내부 Weaviate DB에서 논문 검색.
        이미 수집된 논문의 full-text를 벡터 검색.
        빠르고 관련 스니펫을 바로 반환.
        - 1차 검색에 사용
        - 방법론 분석에 적합 (스니펫 포함)
    """,
    "parameters": {
        "query": "검색 쿼리",
        "year_from": "시작 연도 (optional)",
        "year_to": "종료 연도 (optional)",
        "sections": "검색할 섹션 [abstract, methods, results, discussion]",
        "max_results": "최대 결과 수 (default: 10)"
    }
}

# Tool 2: Europe PMC 검색
search_europe_pmc = {
    "name": "search_europe_pmc",
    "description": """
        Europe PMC API로 Open Access 논문 검색.
        - RAG에 없는 최신 논문 검색
        - Full-text 접근 가능
        - 참조/인용 관계 탐색 가능
        사용 시점:
        - RAG 결과가 부족할 때
        - 특정 논문의 full-text가 필요할 때
        - 인용 네트워크 탐색이 필요할 때
    """,
    "parameters": {
        "query": "검색 쿼리 (Europe PMC 문법)",
        "open_access_only": "OA 논문만 (default: true)",
        "year_from": "시작 연도",
        "year_to": "종료 연도",
        "max_results": "최대 결과 수 (default: 20)"
    }
}

# Tool 3: Europe PMC Full-text 가져오기
get_paper_fulltext = {
    "name": "get_paper_fulltext",
    "description": """
        특정 논문의 full-text를 가져옴.
        PMC ID가 있는 Open Access 논문만 가능.
        - 방법론 상세 분석
        - 특정 섹션 추출
    """,
    "parameters": {
        "pmc_id": "PMC ID (예: PMC1234567)",
        "sections": "추출할 섹션 (optional)"
    }
}

# Tool 4: 웹 검색 (Tavily)
search_web = {
    "name": "search_web",
    "description": """
        Tavily API로 일반 웹 검색.
        - 논문 외 자료 (프로토콜, 가이드라인, 최신 뉴스)
        - 검색 + 요약 통합 제공
        - 월 1,000회 무료 한도 내에서만 사용
        사용 시점:
        - 실험 프로토콜/방법론 검색
        - 최신 연구 동향/뉴스
        - RAG, Europe PMC로 부족할 때
        주의: 무료 한도 초과 시 자동 skip
    """,
    "parameters": {
        "query": "검색 쿼리",
        "search_depth": "basic | advanced (default: basic)",
        "max_results": "최대 결과 수 (default: 5)"
    }
}
```

#### 4.1.4 검색 승격 규칙 (DP1 Router)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Tier 승격 규칙 (Search Escalation)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  기본 원칙:                                                             │
│  ──────────                                                             │
│  1. 항상 1차(RAG)부터 시작                                              │
│  2. 부족하면 2차(Europe PMC)로 승격                                     │
│  3. 그래도 부족하면 3차(Tavily)로 승격 (월 1,000회 내에서만)            │
│  4. 한도 초과 시 → 3차 skip + "근거 부족" 태그 + Plan B로 진행          │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  입력 피처 (3개):                                                       │
│  ────────────────                                                       │
│  1. coverage_score (0~1)                                                │
│     └─ Decompose Tests의 질문(Q1~Qn) 중 "근거가 붙은 질문 비율"         │
│                                                                         │
│  2. evidence_density                                                    │
│     └─ 질문별 EvidenceSnippet 수 (특히 PERTURBATION/READOUT)            │
│                                                                         │
│  3. quality_proxy                                                       │
│     └─ top-k 평균 점수 (또는 reranker score)                            │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  승격 조건:                                                             │
│  ──────────                                                             │
│                                                                         │
│  [RAG → Europe PMC]                                                     │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ coverage_score < 0.70                                        │       │
│  │   OR                                                         │       │
│  │ 질문 중 1개라도 evidence_density < 2                         │       │
│  │   OR                                                         │       │
│  │ PERTURBATION/READOUT 스니펫이 전반적으로 부족                │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  [Europe PMC → Web]                                                     │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ Europe PMC 이후에도 coverage_score < 0.75                    │       │
│  │   AND                                                        │       │
│  │ 핵심 질문(Q1/Q2)이 아직 근거 빈약                            │       │
│  │   AND                                                        │       │
│  │ web_budget_remaining > 0                                     │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  [Web budget 없으면]                                                    │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │ search_web SKIP                                              │       │
│  │ "근거 부족/불확실" 표시                                      │       │
│  │ Plan B(보수적)로 synthesis                                   │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 4.1.5 검색 목적별 쿼리 타입 (3종)

| 목적 | 설명 | 강제 포함 키워드 예시 |
|------|------|----------------------|
| `mechanism` | 기전/경로/우회 활성화 | pathway, signaling, activation, bypass |
| `protocol_controls` | 대조군/실험 프로토콜/측정법 | xenograft, cell viability, IC50, phosphorylation, IHC, FISH, copy number |
| `evidence_strength` | 임상/코호트/빈도/역학 근거 | clinical, cohort, prevalence, frequency, patient |

> **DP2(After Critique)에서 `search_for_controls` 할 때 `protocol_controls` 목적 사용**

#### 4.1.6 시스템 가드레일 (Budget 제한)

```python
# 런 단위 제한 (권장)
MAX_WEB_CALLS_PER_RUN = 1      # Web은 run당 최대 1회
MAX_EPMC_CALLS_PER_RUN = 2     # EPMC는 run당 최대 2회 (쿼리 확장 1회 포함)

# 월 단위 제한
WEB_MONTHLY_LIMIT = 1000       # Tavily 무료 한도

# Budget 관리
class SearchBudgetManager:
    """검색 예산 관리 (Redis 카운터)"""

    async def get_web_remaining(self) -> int:
        used = await redis.get("tavily:monthly_used") or 0
        return WEB_MONTHLY_LIMIT - int(used)

    async def can_use_web(self, run_web_count: int) -> bool:
        return (
            run_web_count < MAX_WEB_CALLS_PER_RUN
            and await self.get_web_remaining() > 0
        )

    async def increment_web_usage(self):
        await redis.incr("tavily:monthly_used")
        # 매월 1일에 리셋하는 TTL 또는 cron job 필요
```

#### 4.1.7 Router 출력 스키마 (구조화된 Decision)

```json
{
  "decision": "upgrade_to_epmc",
  "reason": "coverage_score=0.55 and Q2 evidence_density=0",
  "tier": 2,
  "objective": "mechanism",
  "query_plan": {
    "base_terms": ["EGFR T790M", "osimertinib resistance", "MET amplification"],
    "expand_terms": ["bypass signaling", "MET inhibitor", "phospho-MET", "IC50"],
    "filters": {"open_access_only": true}
  },
  "budgets": {
    "web_remaining": 873,
    "epmc_remaining_this_run": 1
  }
}
```

**Decision 선택지:**
- `proceed` - 현재 결과로 충분
- `upgrade_to_epmc` - Europe PMC로 승격
- `upgrade_to_web` - Tavily 웹 검색으로 승격
- `skip_web_limit` - 웹 한도 초과로 skip + Plan B

#### 4.1.8 캐시 전략 (비용 절감)

```python
# 캐시 키 생성
cache_key = hash(
    hypothesis_struct +
    test_questions +
    query_plan +
    tier
)

# TTL 설정
CACHE_TTL = {
    "rag": timedelta(days=7),      # 내부 DB 업데이트 주기에 맞춤
    "epmc": timedelta(days=30),    # OA 논문은 자주 안 바뀜
    "web": timedelta(days=7),      # 변동 가능
}

# 캐시 hit 시 → Tool call 없이 Evidence Pack 재구성
async def search_with_cache(tier: str, query_plan: dict) -> SearchResult:
    cache_key = generate_cache_key(tier, query_plan)

    cached = await redis.get(cache_key)
    if cached:
        logger.info(f"Cache hit for {tier} search")
        return SearchResult.from_cache(cached)

    result = await execute_search(tier, query_plan)
    await redis.setex(cache_key, CACHE_TTL[tier], result.to_json())
    return result
```

#### 4.1.9 Evidence Pack 통합 스키마

```python
@dataclass
class EvidenceSnippet:
    """모든 tier에서 동일한 스키마"""

    # 출처 정보
    source_tier: Literal[1, 2, 3]           # 1=RAG, 2=EPMC, 3=Web
    source_tool: Literal["rag", "epmc", "web"]
    paper_id: str                            # PMID/PMCID/URL

    # 위치 정보
    section: str | None                      # abstract, methods, results, discussion
    offset_start: int | None                 # RAG/EPMC는 있음
    offset_end: int | None
    quote_span: str | None                   # Web은 offset 대신 이것 사용
    url_anchor: str | None                   # Web 결과 추적용

    # 내용 정보
    text: str
    claim_type: str                          # PERTURBATION, READOUT, PROTOCOL 등
    relevance_score: float
```

#### 4.1.10 운영 정책 (MVP 권장)

| 정책 | 설정 | 비고 |
|------|------|------|
| 기본 흐름 | RAG → (필요시) EPMC | Web은 feature flag로 ON/OFF |
| Web 허용 조건 | run당 0~1회, `protocol_controls` 목적만 | MVP 단계 |
| 월 한도 초과 시 | Web 자동 skip + "근거 부족" 표시 + Plan B | graceful degradation |
| 캐시 | 활성화 (비용 50% 절감 기대) | Redis 기반 |

#### 4.1.11 LLM의 Tool 선택 예시

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 시나리오: "MET amplification osimertinib resistance" 검색               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Iteration 1:                                                            │
│   Thought: 먼저 내부 DB에서 검색해보자.                                 │
│   Action: search_rag(query="MET amplification osimertinib resistance")  │
│   Observation: 3개 논문 발견, 커버리지 부족                             │
│                                                                         │
│ Iteration 2:                                                            │
│   Thought: 결과가 부족하다. Europe PMC에서 Open Access 논문을 더 찾자.  │
│   Action: search_europe_pmc(                                            │
│       query="(MET amplification) AND (osimertinib OR AZD9291)",         │
│       year_from=2018,                                                   │
│       open_access_only=true                                             │
│   )                                                                     │
│   Observation: 12개 논문 추가 발견                                      │
│                                                                         │
│ Iteration 3:                                                            │
│   Thought: PMC7654321 논문의 Methods가 우리 실험 설계에 참고할만하다.   │
│            Full-text를 가져와서 상세 분석하자.                          │
│   Action: get_paper_fulltext(pmc_id="PMC7654321", sections=["methods"]) │
│   Observation: Methods 섹션 추출 완료                                   │
│                                                                         │
│ Iteration 4:                                                            │
│   Thought: 이제 충분한 자료가 모였다. 실험 설계로 넘어가자.             │
│   Action: design_experiment(...)                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 전체 Tool Set (확정)

| Tool Name | 카테고리 | 설명 | 상태 | 비용 |
|-----------|----------|------|------|------|
| `search_rag` | 검색 | 내부 Weaviate 벡터 검색 | 기존 | 무료 |
| `search_europe_pmc` | 검색 | Europe PMC Open Access 검색 | 신규 | 무료 |
| `get_paper_fulltext` | 검색 | PMC 논문 Full-text 추출 | 신규 | 무료 |
| `search_web` | 검색 | Tavily 웹 검색 | 신규 | 월 1,000회 무료 |
| `analyze_paper` | 분석 | 특정 논문 심층 분석 | 기존 확장 | 무료 |
| `expand_keywords` | 유틸 | 키워드 동의어 확장 | 기존 | 무료 |
| `design_experiment` | 설계 | 실험 설계 생성 | 기존 | 무료 |
| `critique_design` | 검증 | 설계 비판적 검토 | 기존 | 무료 |
| `identify_measurements` | 설계 | 측정치 식별 | 기존 | 무료 |
| `validate_feasibility` | 검증 | 실현가능성 평가 | 기존 | 무료 |
| `ask_user` | 상호작용 | 사용자에게 질문 | 기존 | 무료 |
| `finish` | 제어 | 작업 완료 | 기존 | 무료 |

#### Tavily 사용량 관리

```python
# Tavily 무료 한도 관리
class TavilyUsageManager:
    MONTHLY_FREE_LIMIT = 1000

    async def can_search(self) -> bool:
        """이번 달 사용량 확인"""
        usage = await self.get_monthly_usage()
        return usage < self.MONTHLY_FREE_LIMIT

    async def search_with_fallback(self, query: str) -> SearchResult:
        """한도 초과 시 graceful skip"""
        if not await self.can_search():
            logger.warning("Tavily monthly limit exceeded, skipping web search")
            return SearchResult(skipped=True, reason="monthly_limit_exceeded")

        return await self.tavily_search(query)
```

### 4.2 Tool 호출 예시

```python
# ReAct 스타일
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": "Search for relevant papers in the database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "year_from": {"type": "integer", "description": "Filter by year (from)"},
                    "max_results": {"type": "integer", "description": "Maximum results"}
                },
                "required": ["query"]
            }
        }
    },
    # ... 다른 tools
]

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    tool_choice="auto"  # LLM이 알아서 tool 선택
)
```

---

## 5. Decision Point 상세 규칙

### 5.1 DP2 (After Critique) — 필수

> **에이전트다움 체감이 가장 큰 지점. 품질/안전도 여기서 잡힘.**

#### 입력 피처

```python
@dataclass
class DP2Input:
    quality_score: float                    # 0~1

    critique_report: CritiqueReport
    # - missing_controls: list[str]
    # - ambiguity_flags: list[str]         # 결과 해석이 여러 가설 만족
    # - confounders: list[str]
    # - evidence_gaps: list[str]           # 특정 질문 근거 부족
    # - feasibility_conflicts: list[str]   # 비용/윤리/시간 충돌

    budgets: BudgetStatus
    # - epmc_remaining: int
    # - web_remaining: int
    # - iteration_remaining: int
```

#### 선택지 (4개 고정)

| Decision | 설명 |
|----------|------|
| `redesign` | 설계/측정치 수정 (기본) |
| `search_for_controls` | 대조군/프로토콜 근거 추가 검색 (Tier 1→2, web 옵션) |
| `ask_user` | 리소스/모델 제약 질문 (최대 3개) |
| `accept_minor_issues` | 경미 이슈 표시하고 synthesis로 |

#### 규칙 (우선순위 순)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Rule 1 — 하드 실패 (무조건 수정/질문)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  missing_controls에 아래가 있으면 → redesign 또는 search_for_controls   │
│    • vehicle control                                                    │
│    • non-targeting control                                              │
│    • positive control                                                   │
│    • rescue (필요한 경우)                                               │
│                                                                         │
│  ambiguity_flags가 핵심 질문(Q1/Q2)에 걸리면                            │
│    → redesign (설계 타입 변경 포함)                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Rule 2 — 근거 갭은 '검색'으로 해결 (가능하면)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  evidence_gaps 있음 AND epmc_remaining > 0                              │
│    → search_for_controls (또는 evidence_strength 목적 검색)             │
│                                                                         │
│  ⚠️ 가드레일: 같은 갭으로 2번 연속 검색 금지                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Rule 3 — feasibility 충돌은 'Plan B'로 다운시프트                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  feasibility_conflicts에 high cost / ethics / IRB 있음                  │
│    AND (approval_status != approved OR 예산/시간 제한 명확)             │
│    → redesign (Plan B 방향: 저비용/비승인으로 강제)                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Rule 4 — 질문은 "정보가치가 클 때만"                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ask_user 조건:                                                         │
│    • 모델(세포/오가노이드/in vivo) 가능 여부 불명확 + 설계 좌우         │
│    • 사용 가능한 assay 제한 → endpoint 정의 불가                        │
│                                                                         │
│  ⚠️ 질문 수 상한: 최대 3개                                              │
│  ⚠️ 답 없으면 가정 기반 진행                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Rule 5 — 경미 이슈 수용 조건                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  quality_score >= 0.8                                                   │
│    AND 하드 실패 없음                                                   │
│    AND 핵심 질문 근거 최소 조건 충족                                    │
│    → accept_minor_issues                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### DP2 출력 스키마

```json
{
  "decision": "search_for_controls",
  "reason": "evidence_gaps=['Q2 lacks protocol reference'] and epmc_remaining=1",
  "details": {
    "target_gaps": ["Q2"],
    "search_objective": "protocol_controls",
    "fallback_if_fail": "redesign"
  },
  "budgets": {
    "epmc_remaining": 1,
    "web_remaining": 873,
    "iteration_remaining": 1
  }
}
```

---

### 5.2 DP3 (Before Synthesis) — Plan A/B용 최소 규칙

> **출력 직전 의사결정. Plan A/B로 가면 UX가 확 좋아지고 Approval Gate와 연결됨.**

#### 선택지 (3개로 단순화)

| Decision | 설명 |
|----------|------|
| `single_plan` | 하나로 정리 (승인 필요 없고 무난할 때) |
| `plan_A_B` | A(강력/비용↑) + B(보수/비용↓) |
| `plan_B_only` | 승인/예산/윤리상 A 불가 |

#### 규칙

```
┌─────────────────────────────────────────────────────────────────────────┐
│ plan_A_B 조건 (둘 중 하나라도 해당)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  • approval_required == True                                            │
│  • feasibility_conflicts에 high cost / ethics 있음                      │
│  • 핵심 질문 해결에 고비용 선택지 존재 (omics, in vivo, external data)  │
│                                                                         │
│  → plan_A_B 출력                                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ plan_B_only 조건 (둘 중 하나라도 해당)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  • web budget exhausted + evidence 부족                                 │
│  • approval_status == rejected (승인 거절/불가)                         │
│  • 명시적 제약 존재 ("in vitro만", "2주 안에")                          │
│                                                                         │
│  → plan_B_only 출력                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ single_plan 조건 (모두 충족)                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  • approval_required == False                                           │
│  • quality_score 높음 (>= 0.8)                                          │
│  • evidence 충분                                                        │
│                                                                         │
│  → single_plan 출력                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### DP3 출력 스키마

```json
{
  "decision": "plan_A_B",
  "reason": "approval_required=True (in vivo experiment included)",
  "plan_config": {
    "plan_a": {
      "label": "강력 검증 (in vivo 포함)",
      "approval_required": true,
      "estimated_cost": "high",
      "questions_covered": ["Q1", "Q2", "Q3"]
    },
    "plan_b": {
      "label": "1차 검증 (in vitro only)",
      "approval_required": false,
      "estimated_cost": "medium",
      "questions_covered": ["Q1", "Q2"],
      "limitations": ["Q3 역학 근거는 문헌 기반만"]
    }
  }
}
```

---

### 5.3 Plan A/B 분기 로직

> **같은 목표를 다른 비용/리스크로 달성하는 2트랙**

#### Plan A vs Plan B 정의

| 구분 | Plan A (강력) | Plan B (보수) |
|------|--------------|---------------|
| **범위** | in vivo, omics, 대규모 코호트, 외부 데이터 | in vitro 위주, public dataset, 최소 readout |
| **장점** | 가설 구분력 최대 | 빠르고 승인 적음 |
| **단점** | 비용↑, 시간↑, 윤리/승인 필요 | 결론 강도 낮음 (불확실성 표시) |
| **승인** | 필요할 수 있음 | 불필요 |

#### Test Question 배분 규칙

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 핵심 질문 (Q1/Q2) 배분                                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Plan A: 핵심 질문 전체 커버 (최적 방법론)                               │
│  Plan B: 핵심 질문 최소 1개씩 커버 (in vitro 대안)                       │
│                                                                         │
│  예시:                                                                  │
│  Q1 (기전) → A: xenograft + phospho-MET IHC                            │
│            → B: cell line + Western blot                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 보조 질문 (Q3 역학/빈도) 배분                                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Plan A: cohort / ctDNA / real-world data                               │
│  Plan B: 문헌 기반 빈도 요약 + 공개 데이터 (가능 시)                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Plan 출력 예시

```markdown
## Plan A: 강력 검증 (승인 필요)

### 실험 1: Xenograft 모델 MET inhibitor 병용
- **목적**: Q1 (기전) + Q2 (치료) 동시 검증
- **방법**: PDX 모델, osimertinib + savolitinib 병용
- **측정**: 종양 부피, phospho-MET IHC, survival
- **예상 기간**: 8주
- **비용**: High
- ⚠️ **IRB 승인 필요**

---

## Plan B: 1차 검증 (승인 불필요)

### 실험 1: Cell viability assay
- **목적**: Q1 (기전) 1차 검증
- **방법**: H1975 + HCC827 cell line, MTT assay
- **측정**: IC50, combination index
- **예상 기간**: 2주
- **비용**: Low

### 실험 2: Western blot
- **목적**: Q2 (치료) 기전 확인
- **방법**: MET/EGFR pathway 마커
- **측정**: phospho-MET, phospho-EGFR, cleaved caspase-3
- **예상 기간**: 1주
- **비용**: Low

⚠️ **제한사항**: Q3 역학 근거는 문헌 기반 요약만 포함
```

---

### 5.4 운영 가드레일 (DP2/DP3)

| 항목 | 제한 |
|------|------|
| DP2 루프 | 최대 2회 |
| DP3 | 1회만 (출력 직전) |
| Plan A | `approval_required`면 자동 "승인 필요" 배지 |
| Plan B | 언제나 생성 가능 (최악의 경우에도 결과물 보장) |
| ask_user 질문 | 최대 3개, 답 없으면 가정 기반 진행 |
| 같은 gap 연속 검색 | 금지 (2번 연속 불가) |

---

## 6. 구현 복잡도 비교

| 항목 | Option A (ReAct) | Option B (Plan-Execute) | Option C (Hybrid) |
|------|------------------|------------------------|-------------------|
| 코드 변경량 | 🔴 대규모 | 🟡 중간 | 🟢 소규모 |
| 기존 코드 재사용 | 20% | 50% | 80% |
| 구현 난이도 | 상 | 중상 | 중 |
| 예상 소요 시간 | 2-3주 | 1-2주 | 3-5일 |
| 토큰 비용 증가 | +200~300% | +50~100% | +30~50% |
| 디버깅 난이도 | 상 | 중 | 하 |

---

## 6. 권장 사항

### 6.1 단기 (이번 주)

**Option C (하이브리드) + 다중 검색 소스** 권장

이유:
- 기존 작동하는 코드 유지
- 빠르게 개선 효과 확인 가능
- 위험 최소화

구현 범위:
1. **다중 검색 Tool 구현**
   - `search_europe_pmc` - Europe PMC API 연동
   - `get_paper_fulltext` - Full-text 추출
   - `search_google_scholar` - (선택) Google Scholar 연동

2. **Tool Registry 구조 추가**
   - 검색 Tool들을 통합 관리
   - Tool 실행 결과 표준화

3. **3개 주요 Decision Point에 LLM 동적 판단 추가**
   - After Search: 어떤 소스로 추가 검색할지 결정
   - After Critique: 수정 전략 결정
   - Before Synthesis: 최종 확인

### 6.2 중기 (다음 달)

**Option B (Plan-and-Execute)** 도입 검토

이유:
- 사용자에게 계획 미리 공유 (투명성)
- 복잡한 가설에 대한 맞춤 계획
- Option C 경험을 바탕으로 안정적 전환

### 6.3 장기 (분기 내)

**Option A (ReAct)** 부분 도입 검토

이유:
- 특정 복잡한 케이스에만 적용
- 완전 자율 에이전트 경험 제공
- 연구용/데모용으로 활용

---

## 7. 확정 사항 및 다음 단계

### 7.1 확정된 사항

| 항목 | 결정 |
|------|------|
| 아키텍처 | **Option C (하이브리드)** - 기존 파이프라인 + Decision Point |
| 검색 스택 | **RAG + Europe PMC + Tavily** (Google Scholar 제외) |
| Tavily 정책 | 월 1,000회 무료 한도, run당 최대 1회, `protocol_controls` 목적만 |
| EPMC 정책 | run당 최대 2회 (쿼리 확장 1회 포함) |
| 캐시 | Redis 기반, TTL: RAG 7일 / EPMC 30일 / Web 7일 |
| 한도 초과 대응 | Web skip + "근거 부족" 표시 + Plan B(보수적) 제공 |

### 7.2 검색 승격 규칙 요약

```
RAG (1차)
    │
    ├─ coverage < 0.70 OR evidence_density < 2 OR PERTURBATION/READOUT 부족
    ▼
Europe PMC (2차)
    │
    ├─ coverage < 0.75 AND 핵심 질문 근거 빈약 AND web_budget > 0
    ▼
Tavily Web (3차)
    │
    └─ budget 없으면 → SKIP + Plan B
```

### 7.3 검색 목적 타입

| 목적 | 사용 시점 |
|------|----------|
| `mechanism` | 기전/경로 검색 |
| `protocol_controls` | 대조군/프로토콜 검색 (DP2에서 주로 사용) |
| `evidence_strength` | 임상/역학 근거 검색 |

### 7.4 Decision Point 요약

| DP | 목적 | 선택지 | 필수 여부 |
|----|------|--------|----------|
| **DP1** | 검색 승격 결정 | proceed / upgrade_to_epmc / upgrade_to_web / skip_web_limit | ✅ 필수 |
| **DP2** | Critique 후 전략 | redesign / search_for_controls / ask_user / accept_minor_issues | ✅ 필수 |
| **DP3** | 출력 형태 결정 | single_plan / plan_A_B / plan_B_only | ✅ 필수 |

### 7.5 Plan A/B 요약

| Plan | 특성 | 승인 | 비용 |
|------|------|------|------|
| **Plan A** | 강력 검증 (in vivo, omics) | 필요할 수 있음 | High |
| **Plan B** | 보수 검증 (in vitro only) | 불필요 | Low |

> **Plan B는 항상 생성 가능** — 최악의 경우에도 결과물 보장

### 7.6 구현 우선순위 (확정)

```
Phase 1: 검색 인프라
─────────────────────
1. search_europe_pmc - Europe PMC API
2. get_paper_fulltext - Full-text 추출
3. search_web - Tavily (budget 관리 포함)
4. Budget Manager - Redis 카운터 + 캐시

Phase 2: Decision Points
─────────────────────────
5. DP1 Router - 검색 승격 로직
6. DP2 Router - Critique 후 전략 (핵심!)
7. DP3 Router - Plan A/B 분기

Phase 3: 통합
──────────────
8. Evidence Pack 3-tier 통합
9. Plan A/B 출력 포맷
10. Approval Gate 연동
```

### 7.7 가드레일 요약

| 항목 | 제한 |
|------|------|
| Web (Tavily) | run당 1회, 월 1,000회 |
| EPMC | run당 2회 |
| DP2 루프 | 최대 2회 |
| DP3 | 1회만 |
| ask_user | 최대 3개 질문 |
| 캐시 TTL | RAG 7일, EPMC 30일, Web 7일 |

---

## 8. 참고 자료

- [ReAct Paper](https://arxiv.org/abs/2210.03629) - Reasoning + Acting
- [Plan-and-Solve](https://arxiv.org/abs/2305.04091) - Planning approach
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/) - 현재 사용 중인 프레임워크
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
