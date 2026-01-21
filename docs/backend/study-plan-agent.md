# Study Plan Agent 설계 문서

> **Version**: 2.1
> **Status**: Draft
> **Created**: 2025-01-21
> **Last Updated**: 2025-01-21
> **Author**: AI Assistant

---

## 1. 개요

### 1.1 목적

Study Plan Agent는 **연구자가 입력한 가설이나 기전(Mechanism)을 기반으로 후속 실험 설계 초안과 필요한 데이터/측정치를 자동으로 제안**하는 **주도적(Proactive/Agentic) 에이전트**입니다.

### 1.2 핵심 가치

| 문제 | 솔루션 |
|------|--------|
| 연구자가 가설 검증 실험 설계에 많은 시간 소요 | AI가 관련 논문 기반 실험 설계 초안 제공 |
| 필요한 측정치/바이오마커 누락 위험 | 유사 연구의 실험 방법론 분석하여 제안 |
| 기존 연구 방법론 탐색 비효율 | RAG 기반 관련 논문 자동 검색 및 분석 |
| 실험 설계의 논리적 허점 | 자기검증(Critic) 노드로 품질 보장 |
| 검색 결과 부족 | 자동 쿼리 확장 및 재검색 루프 |

### 1.3 "주도적(Agentic)" 에이전트의 핵심 특성

단순 순차 실행이 아닌, **반복 루프 + 판단 게이트 + 자기검증**을 통한 주도성 확보:

| 특성 | 구현 방식 |
|------|----------|
| **검증 질문 분해** | 가설 → Necessity/Sufficiency/Epistasis/Specificity 테스트 분해 |
| **검색 커버리지 루프** | coverage_score < 0.6이면 쿼리 확장 후 재검색 |
| **Evidence Pack 구축** | 근거를 claim_type별로 분리하여 추적 가능하게 |
| **자기검증 (Critic)** | 설계 후 대조군/구분력/모호성 스스로 검증 + 수정 루프 |
| **승인 게이트** | 비용/윤리 큰 단계는 선택지와 함께 사용자 승인 요청 |

### 1.4 사용 시나리오

```
연구자 입력:
"EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로
MET amplification이 관여한다는 가설을 검증하고 싶습니다."

Study Plan Agent 출력:
1. 가설 구조화 (독립변수, 종속변수, 매개변수)
2. 검증 질문 분해 (Necessity, Sufficiency, Epistasis, Specificity) + decision_rule
3. 유사 연구 검색 (커버리지 부족 시 자동 확장)
4. Evidence Pack 구축 (model/perturbation/readout/result별 스니펫)
5. 실험 설계 초안 (in vitro, in vivo, clinical)
6. 자기검증 (대조군, 구분력, 모호성) + 수정 루프
7. 필요 데이터/측정치 목록
8. 실현 가능성 + 승인 게이트 (선택지 제공)
9. 최종 계획서 + Evidence Trace
```

---

## 2. 아키텍처

### 2.1 전체 흐름 (3개 루프 + 승인 게이트)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 입력                                    │
│  (가설/기전 설명, 연구 맥락, 제약조건)                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [parse_hypothesis]         │
              │   가설 구조화 + 동의어 확장   │
              └──────────────┬──────────────┘
                             │
                    ┌────────┴────────┐
                    │ confidence < 0.7?│
                    └────────┬────────┘
                      Yes    │    No
              ┌──────────────▼──┐    │
              │ [clarify_       │    │
              │  hypothesis]    │◄───┘
              │ 사용자에게 질문  │
              └────────┬────────┘
                       │ (사용자 응답 후 재시도)
                       ▼
              ┌──────────────────────────────┐
              │   [decompose_to_test_        │
              │    questions]                │
              │   Necessity/Sufficiency/     │
              │   Epistasis/Specificity      │
              │   + decision_rule            │
              └──────────────┬───────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [search_prior_studies]     │◄─────────────┐
              │   유사 연구 RAG 검색          │              │
              └──────────────┬──────────────┘              │
                             │                             │
                    ┌────────┴────────┐                    │
                    │ coverage < 0.6? │                    │
                    └────────┬────────┘                    │
                      Yes    │    No                       │
              ┌──────────────▼──┐    │                     │
              │ [expand_search] │────┘                     │
              │ 쿼리 확장       │ ─────────────────────────┘
              └─────────────────┘      (Loop 1: 검색 확장)
                             │
              ┌──────────────▼──────────────┐
              │   [build_evidence_pack]      │
              │   근거 스니펫 수집/분류       │
              │   (model/perturb/readout/   │
              │    result별 분리)            │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [analyze_methodologies]    │
              │   방법론 분석 + 패턴 추출    │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [design_experiments]       │◄─────────────┐
              │   실험 설계 초안 생성         │              │
              └──────────────┬──────────────┘              │
                             │                             │
              ┌──────────────▼──────────────┐              │
              │   [critique_and_refine]      │              │
              │   대조군/구분력/모호성 검증   │              │
              └──────────────┬──────────────┘              │
                             │                             │
                    ┌────────┴────────┐                    │
                    │ quality >= 0.8  │                    │
                    │ OR retry >= 2?  │                    │
                    └────────┬────────┘                    │
                      No     │    Yes                      │
                  ┌──────────▼──┐    │                     │
                  │ revision++  │────┘                     │
                  └─────────────┘ ─────────────────────────┘
                             │        (Loop 2: Critic 수정)
              ┌──────────────▼──────────────┐
              │   [identify_measurements]    │
              │   필요 데이터/측정치 도출     │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [validate_feasibility]     │
              │   실현 가능성 평가            │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [approval_gate]            │
              │   비용/윤리/데이터 승인 판단  │
              └──────────────┬──────────────┘
                             │
                    ┌────────┴────────┐
                    │ approval_status │
                    └────────┬────────┘
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
       "approved"      "needs_user"      "rejected"
            │                │                │
            │     ┌──────────▼──────────┐     │
            │     │ SSE: 승인 요청       │     │
            │     │ + choices 제공      │     │
            │     │ (사용자 응답 대기)   │     │
            │     └──────────┬──────────┘     │
            │                │                │
            │    (사용자 승인/범위축소/대안)    │
            │                │                │
            └────────────────┼────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   [synthesize_plan]          │
              │   최종 연구 계획서 생성       │
              │   + Evidence Trace 매핑      │
              └──────────────────────────────┘
```

### 2.2 LangGraph 그래프 구조

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(StudyPlanState)

# ============================================================
# 노드 등록 (12개)
# ============================================================
graph.add_node("parse_hypothesis", parse_hypothesis_node)
graph.add_node("clarify_hypothesis", clarify_hypothesis_node)
graph.add_node("decompose_to_test_questions", decompose_test_questions_node)
graph.add_node("search_prior_studies", search_prior_studies_node)
graph.add_node("expand_search", expand_search_node)                    # NEW
graph.add_node("build_evidence_pack", build_evidence_pack_node)        # NEW (별도 분리)
graph.add_node("analyze_methodologies", analyze_methodologies_node)
graph.add_node("design_experiments", design_experiments_node)
graph.add_node("critique_and_refine", critique_and_refine_node)
graph.add_node("identify_measurements", identify_measurements_node)
graph.add_node("validate_feasibility", validate_feasibility_node)
graph.add_node("approval_gate", approval_gate_node)                    # NEW (별도 분리)
graph.add_node("synthesize_plan", synthesize_plan_node)

# ============================================================
# 조건부 라우팅 함수
# ============================================================

def route_after_parse(state: StudyPlanState) -> str:
    """가설 파싱 후 라우팅"""
    if state.get("clarification_needed", False):
        return "clarify"
    return "ok"

def route_after_search(state: StudyPlanState) -> str:
    """검색 후 커버리지 기반 라우팅"""
    coverage = state.get("search_coverage_score", 1.0)
    expand_count = state.get("search_expand_count", 0)

    if coverage < 0.6 and expand_count < 2:  # 최대 2회 확장
        return "expand"
    return "ok"

def route_after_critique(state: StudyPlanState) -> str:
    """Critic 후 품질 기반 라우팅"""
    quality = state.get("quality_score", 0.0)
    revision_count = state.get("revision_count", 0)

    if quality >= 0.8 or revision_count >= 2:
        return "pass"
    return "revise"

def route_after_approval(state: StudyPlanState) -> str:
    """승인 게이트 후 라우팅"""
    return state.get("approval_status", "approved")

# ============================================================
# 엣지 연결
# ============================================================

# 시작 → 가설 파싱
graph.add_edge(START, "parse_hypothesis")

# 가설 명확성 분기
graph.add_conditional_edges(
    "parse_hypothesis",
    route_after_parse,
    {
        "clarify": "clarify_hypothesis",
        "ok": "decompose_to_test_questions",
    }
)
graph.add_edge("clarify_hypothesis", "parse_hypothesis")  # 재파싱

# 검증 질문 분해 → 검색
graph.add_edge("decompose_to_test_questions", "search_prior_studies")

# 검색 커버리지 루프 (Loop 1)
graph.add_conditional_edges(
    "search_prior_studies",
    route_after_search,
    {
        "expand": "expand_search",
        "ok": "build_evidence_pack",
    }
)
graph.add_edge("expand_search", "search_prior_studies")

# Evidence Pack → 방법론 분석 → 실험 설계
graph.add_edge("build_evidence_pack", "analyze_methodologies")
graph.add_edge("analyze_methodologies", "design_experiments")

# 실험 설계 → Critic
graph.add_edge("design_experiments", "critique_and_refine")

# Critic 루프 (Loop 2)
graph.add_conditional_edges(
    "critique_and_refine",
    route_after_critique,
    {
        "pass": "identify_measurements",
        "revise": "design_experiments",  # 재설계
    }
)

# 측정치 → 실현가능성 → 승인 게이트
graph.add_edge("identify_measurements", "validate_feasibility")
graph.add_edge("validate_feasibility", "approval_gate")

# 승인 게이트 분기
graph.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {
        "approved": "synthesize_plan",
        "needs_user": END,  # SSE로 승인 요청 후 중단 (사용자 응답 후 재시작)
        "rejected": END,    # 거부됨 (대안 제시 후 종료)
    }
)

# 최종 합성 → 종료
graph.add_edge("synthesize_plan", END)
```

---

## 3. 상태 (State) 정의

### 3.1 핵심 데이터 구조

```python
from typing import TypedDict, Literal
from dataclasses import dataclass, field
from enum import Enum

# ============================================================
# Enums
# ============================================================

class ExperimentType(str, Enum):
    IN_VITRO = "in_vitro"
    IN_VIVO = "in_vivo"
    CLINICAL = "clinical"
    COMPUTATIONAL = "computational"

class EvidenceLevel(str, Enum):
    HIGH = "high"           # RCT, Meta-analysis
    MODERATE = "moderate"   # Cohort, Case-control
    LOW = "low"             # Case series, Expert opinion
    PRECLINICAL = "preclinical"

class TestCategory(str, Enum):
    """검증 질문 카테고리"""
    NECESSITY = "necessity"       # X 막으면 phenotype 사라지나?
    SUFFICIENCY = "sufficiency"   # X 올리면 phenotype 생기나?
    EPISTASIS = "epistasis"       # X가 Y 위/아래? (directionality)
    SPECIFICITY = "specificity"   # off-target / 다른 세포타입 재현?

class ClaimType(str, Enum):
    """Evidence Snippet의 주장 유형"""
    MODEL = "model"               # 어떤 모델을 썼는지
    PERTURBATION = "perturbation" # 어떤 perturbation을 썼는지
    READOUT = "readout"           # 어떤 readout을 봤는지
    RESULT = "result"             # 결과/결론
    LIMITATION = "limitation"     # 한계점

class CostBucket(str, Enum):
    LOW = "low"           # < $10K
    MEDIUM = "medium"     # $10K - $50K
    HIGH = "high"         # $50K - $200K
    VERY_HIGH = "very_high"  # > $200K

class EthicsBucket(str, Enum):
    NONE = "none"
    IACUC = "iacuc"           # 동물실험위원회
    IRB_EXPEDITED = "irb_expedited"
    IRB_FULL = "irb_full"

class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    NEEDS_USER = "needs_user"
    REJECTED = "rejected"

# ============================================================
# 가설 관련 구조체
# ============================================================

@dataclass
class HypothesisStructure:
    """구조화된 가설"""
    original_text: str
    independent_variable: str
    dependent_variable: str
    mediating_variables: list[str] = field(default_factory=list)
    moderating_variables: list[str] = field(default_factory=list)
    population: str = ""
    mechanism_pathway: str = ""
    keywords: list[str] = field(default_factory=list)
    # 동의어/표준화된 키워드
    expanded_keywords: list[str] = field(default_factory=list)
    gene_aliases: list[str] = field(default_factory=list)
    pathway_names: list[str] = field(default_factory=list)
    assay_keywords: list[str] = field(default_factory=list)

@dataclass
class TestQuestion:
    """검증 질문 (decision_rule 포함)"""
    category: TestCategory
    question: str                         # "MET을 억제하면 osimertinib 민감성이 회복되는가?"
    rationale: str                        # 왜 이 질문이 중요한가
    decision_rule: str                    # "IC50 50% 감소 시 가설 지지, 변화 없으면 반박"
    suggested_approach: str               # 검증 접근법 제안
    priority: int = 1                     # 1=필수, 2=권장, 3=선택

# ============================================================
# Evidence 관련 구조체
# ============================================================

@dataclass
class EvidenceSnippet:
    """근거 스니펫 - 정확한 출처 추적"""
    snippet_id: str                       # 고유 ID
    paper_id: str                         # "pmid:12345678"
    section: str                          # "methods", "results"
    offset_start: int                     # UTF-8 문자 위치
    offset_end: int
    claim_type: ClaimType                 # model/perturbation/readout/result/limitation
    text: str                             # 실제 텍스트 (짧게, 저작권 고려)
    relevance_score: float = 0.0

@dataclass
class EvidencePack:
    """논문별 Evidence 묶음"""
    paper_id: str
    title: str
    journal: str
    year: int
    snippets: list[EvidenceSnippet] = field(default_factory=list)
    # claim_type별 요약
    model_used: str = ""
    perturbation_used: str = ""
    readout_used: str = ""
    key_finding: str = ""
    limitations: list[str] = field(default_factory=list)

@dataclass
class EvidenceSummaryByClaim:
    """claim_type별 Evidence 요약"""
    models: list[dict] = field(default_factory=list)        # [{paper_id, model, snippet_id}]
    perturbations: list[dict] = field(default_factory=list)
    readouts: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    limitations: list[dict] = field(default_factory=list)

# ============================================================
# 실험 설계 관련 구조체
# ============================================================

@dataclass
class ExperimentDesign:
    """실험 설계 초안"""
    experiment_id: str                    # "exp_1_in_vitro"
    experiment_type: ExperimentType
    title: str
    objective: str
    hypothesis_tested: str
    test_category: TestCategory           # 어떤 검증 질문을 테스트하는지

    # 실험 그룹 (상세화)
    experimental_groups: list[dict] = field(default_factory=list)
    control_groups: list[dict] = field(default_factory=list)
    # control_groups 예시:
    # [
    #   {"type": "negative", "name": "Untreated", "n": 6},
    #   {"type": "vehicle", "name": "DMSO", "n": 6},
    #   {"type": "positive", "name": "Known inhibitor", "n": 6},
    #   {"type": "non_targeting", "name": "siRNA-NC", "n": 6},
    #   {"type": "rescue", "name": "MET overexpression rescue", "n": 6}
    # ]

    # 방법론
    model_system: str = ""
    treatment_protocol: str = ""
    duration: str = ""

    # 분석
    primary_endpoint: str = ""
    secondary_endpoints: list[str] = field(default_factory=list)
    statistical_approach: str = ""
    sample_size_justification: str = ""

    # 메타
    estimated_timeline: str = ""
    estimated_cost_level: CostBucket = CostBucket.MEDIUM
    technical_difficulty: str = ""

    # 근거 연결
    evidence_snippet_ids: list[str] = field(default_factory=list)
    based_on_studies: list[str] = field(default_factory=list)

# ============================================================
# Critique 관련 구조체
# ============================================================

@dataclass
class CritiqueReport:
    """Critic 상세 보고서"""
    # 대조군 검사 (확장)
    missing_controls: list[str] = field(default_factory=list)
    # ["vehicle", "positive", "non_targeting", "rescue"]

    # 해석 모호성
    ambiguity_issues: list[str] = field(default_factory=list)
    # "이 결과가 A와 B 가설 모두 지지함"

    # 교란변수
    confounders: list[str] = field(default_factory=list)

    # 구분력 (discriminative power)
    discriminative_power_issues: list[str] = field(default_factory=list)
    # "sample size가 20% 차이 검출에 부족"

    # 측정치-가설 정렬
    endpoint_alignment_issues: list[str] = field(default_factory=list)
    # "IC50만으론 기전 확인 불가, pathway marker 필요"

    # 실현가능성 충돌
    feasibility_conflicts: list[str] = field(default_factory=list)

@dataclass
class CritiqueResult:
    """Critic 검증 결과"""
    quality_score: float                  # 0-1 (0.8 이상이면 pass)
    critique_report: CritiqueReport
    revision_suggestions: list[str] = field(default_factory=list)
    passed: bool = False

@dataclass
class RevisionRecord:
    """수정 이력"""
    revision_number: int
    changes_made: list[str]               # 무엇을 바꿨는지
    reason: str                           # 왜 바꿨는지
    quality_before: float
    quality_after: float

# ============================================================
# 승인 게이트 관련 구조체
# ============================================================

@dataclass
class ApprovalItem:
    """승인 필요 항목"""
    item_type: str                        # "in_vivo", "omics", "clinical_data", "high_cost"
    reason: str                           # "IACUC 필요", "RNA-seq 예산/분석 필요"
    cost_bucket: CostBucket
    ethics_bucket: EthicsBucket = EthicsBucket.NONE

@dataclass
class ApprovalChoice:
    """사용자에게 제공할 선택지"""
    choice_id: str                        # "approve_all", "reduce_scope", "alternative"
    label: str                            # "승인하고 진행"
    description: str                      # "예상 비용 $80K, 기간 6개월"
    estimated_cost: str
    estimated_timeline: str

@dataclass
class ApprovalGateResult:
    """승인 게이트 결과"""
    approval_required: bool
    approval_items: list[ApprovalItem] = field(default_factory=list)
    choices: list[ApprovalChoice] = field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    user_decision: dict | None = None     # 사용자 선택 결과

# ============================================================
# 측정 및 실현가능성 관련 구조체
# ============================================================

@dataclass
class MeasurementItem:
    """측정 항목"""
    category: str                         # "biomarker", "clinical", "molecular"
    name: str
    method: str
    rationale: str
    timing: str
    expected_change: str
    reference_range: str | None = None
    evidence_snippet_ids: list[str] = field(default_factory=list)
    based_on_studies: list[str] = field(default_factory=list)

@dataclass
class FeasibilityAssessment:
    """실현 가능성 평가"""
    overall_score: float
    technical_feasibility: float
    technical_concerns: list[str] = field(default_factory=list)
    resource_feasibility: float
    resource_concerns: list[str] = field(default_factory=list)
    timeline_feasibility: float
    timeline_concerns: list[str] = field(default_factory=list)
    ethical_considerations: list[str] = field(default_factory=list)
    alternative_approaches: list[str] = field(default_factory=list)
    risk_mitigation: list[str] = field(default_factory=list)

# ============================================================
# 메인 State
# ============================================================

class StudyPlanState(TypedDict, total=False):
    """Study Plan Agent 상태 v2.1"""

    # === 입력 ===
    user_input: str
    research_context: str | None
    constraints: list[str]
    preferred_experiment_types: list[ExperimentType]

    # === Node 1: parse_hypothesis ===
    hypothesis: HypothesisStructure | None
    hypothesis_confidence: float
    clarification_needed: bool
    clarification_questions: list[str]
    user_clarification: str | None

    # === Node 2: decompose_to_test_questions ===
    test_questions: list[TestQuestion]

    # === Node 3: search_prior_studies ===
    search_queries: list[str]
    prior_studies: list[dict]             # 간단한 메타데이터
    search_coverage_score: float          # 0-1 (0.6 미만이면 확장)
    search_gap_notes: list[str]           # 커버리지 부족 영역
    search_expand_count: int              # 확장 횟수

    # === Node 4: expand_search ===
    expanded_queries: list[str]

    # === Node 5: build_evidence_pack ===
    evidence_snippets: list[EvidenceSnippet]
    evidence_packs: list[EvidencePack]
    evidence_summary: EvidenceSummaryByClaim | None

    # === Node 6: analyze_methodologies ===
    methodology_patterns: list[dict]
    common_biomarkers: list[str]
    common_techniques: list[str]
    methodology_gaps: list[str]

    # === Node 7: design_experiments ===
    experiment_designs: list[ExperimentDesign]
    design_rationale: str

    # === Node 8: critique_and_refine ===
    critique_result: CritiqueResult | None
    quality_score: float                  # 편의 필드
    revision_count: int
    revision_history: list[RevisionRecord]

    # === Node 9: identify_measurements ===
    measurements: list[MeasurementItem]
    measurement_priority: list[str]

    # === Node 10: validate_feasibility ===
    feasibility: FeasibilityAssessment | None

    # === Node 11: approval_gate ===
    approval_gate_result: ApprovalGateResult | None
    approval_status: ApprovalStatus
    approval_log: list[dict]              # 승인 요청/응답 기록

    # === Node 12: synthesize_plan ===
    final_plan: str
    executive_summary: str
    references: list[dict]
    evidence_trace: dict                  # {문장/섹션 ID: [snippet_id, ...]}

    # === 메타데이터 ===
    conversation_id: str | None
    user_id: str | None
    created_at: str
    total_duration_ms: int
    error: str | None

    # === 운영/추적 필드 ===
    run_version: str
    model_versions: dict[str, str]        # {"parse": "gpt-4o", "critique": "gpt-4o"}
    token_usage: dict[str, int]           # {"prompt": 5000, "completion": 3000}
    cost_estimate: float
    status_detail: str
```

---

## 4. 노드 상세 설계

### 4.1 Node 2: decompose_to_test_questions (검증 질문 분해)

**목적**: 가설을 **Necessity/Sufficiency/Epistasis/Specificity** + **decision_rule**로 분해

**출력 규약**:
- 최소 4개 카테고리에서 각 1개 이상
- 각 질문에 `decision_rule` 필수 (어떤 결과면 가설 지지/반박?)

**프롬프트 (DECOMPOSE_TEST_QUESTIONS_SYSTEM)**:

```python
DECOMPOSE_TEST_QUESTIONS_SYSTEM = """You are an expert at designing hypothesis-driven experiments.
Decompose the hypothesis into specific testable questions with clear decision rules.

## Test Categories (Required - at least 1 each)

1. **NECESSITY**: "X를 막으면 phenotype이 사라지는가?"
   - 예: "MET을 억제하면 osimertinib 민감성이 회복되는가?"
   - decision_rule: "IC50 50% 이상 감소 시 가설 지지, 변화 없으면 반박"

2. **SUFFICIENCY**: "X를 올리면 phenotype이 생기는가?"
   - 예: "MET을 과발현시키면 osimertinib 내성이 발생하는가?"
   - decision_rule: "IC50 5배 이상 증가 시 가설 지지, 2배 미만이면 반박"

3. **EPISTASIS**: "X가 Y의 위/아래에 있는가?" (경로 상 순서)
   - 예: "MET amplification이 EGFR의 downstream bypass인가?"
   - decision_rule: "MET 억제 시 pAKT 감소하면 가설 지지, EGFR 억제 시만 감소하면 반박"

4. **SPECIFICITY**: "off-target effect 없이 특이적인가?"
   - 예: "MET 억제 효과가 MET-amplified 세포에서만 나타나는가?"
   - decision_rule: "MET-amp 세포에서만 synergy 있으면 가설 지지, MET-WT에서도 효과 있으면 반박"

## Output Format (JSON)

{
  "test_questions": [
    {
      "category": "necessity",
      "question": "MET을 siRNA/약물로 억제하면 osimertinib 민감성이 회복되는가?",
      "rationale": "MET이 내성의 필요조건인지 확인",
      "decision_rule": "IC50 50% 이상 감소 시 가설 지지, 20% 미만 변화 시 가설 반박",
      "suggested_approach": "MET siRNA knockdown + osimertinib dose-response curve",
      "priority": 1
    },
    ...
  ]
}
"""
```

---

### 4.2 Node 3-4: search_prior_studies + expand_search (검색 루프)

**검색 커버리지 루프**:
- `search_coverage_score < 0.6`이면 쿼리 확장 후 재검색
- 최대 2회 확장

```python
async def search_prior_studies_node(state: StudyPlanState) -> dict:
    """유사 연구 RAG 검색"""
    hypothesis = state["hypothesis"]
    expanded_queries = state.get("expanded_queries", [])

    # 기존 쿼리 + 확장된 쿼리 병합
    all_queries = generate_base_queries(hypothesis) + expanded_queries

    results = await asyncio.gather(*[
        rag_service.retrieve(query=q, top_k=10, use_reranker=True)
        for q in all_queries
    ])

    # 커버리지 평가
    coverage_score, gap_notes = assess_coverage(
        results,
        test_questions=state.get("test_questions", [])
    )

    return {
        "search_queries": all_queries,
        "prior_studies": extract_studies(results),
        "search_coverage_score": coverage_score,
        "search_gap_notes": gap_notes,
        "search_expand_count": state.get("search_expand_count", 0)
    }

async def expand_search_node(state: StudyPlanState) -> dict:
    """검색 쿼리 확장"""
    gap_notes = state.get("search_gap_notes", [])
    hypothesis = state["hypothesis"]

    # 부족한 영역에 대한 추가 쿼리 생성
    new_queries = generate_expansion_queries(gap_notes, hypothesis)

    return {
        "expanded_queries": new_queries,
        "search_expand_count": state.get("search_expand_count", 0) + 1
    }

def assess_coverage(results, test_questions) -> tuple[float, list[str]]:
    """검색 커버리지 평가"""
    # 각 test_question에 대해 관련 논문이 있는지 확인
    covered = 0
    gaps = []

    for tq in test_questions:
        if has_relevant_study(results, tq):
            covered += 1
        else:
            gaps.append(f"'{tq.category}' 검증 관련 연구 부족")

    score = covered / len(test_questions) if test_questions else 1.0
    return score, gaps
```

---

### 4.3 Node 5: build_evidence_pack (Evidence Pack 구축)

**목적**: 검색 결과에서 **claim_type별로 Evidence 스니펫 분리**

**출력 규약**:
- 모든 스니펫에 `snippet_id`, `offset`, `claim_type` 포함
- `evidence_summary`에 claim_type별 요약

```python
async def build_evidence_pack_node(state: StudyPlanState) -> dict:
    """Evidence Pack 구축 - claim_type별 분리"""

    prior_studies = state["prior_studies"]
    all_snippets = []
    all_packs = []

    for study in prior_studies:
        pack = EvidencePack(
            paper_id=study["paper_id"],
            title=study["title"],
            journal=study["journal"],
            year=study["year"]
        )

        # RAG 결과에서 스니펫 추출
        for ref in study.get("references", []):
            snippet = EvidenceSnippet(
                snippet_id=f"{study['paper_id']}_{ref['section']}_{ref['offset_start']}",
                paper_id=study["paper_id"],
                section=ref["section"],
                offset_start=ref["offset_start"],
                offset_end=ref["offset_end"],
                claim_type=classify_claim_type(ref["text"]),
                text=ref["text"][:500],  # 길이 제한
                relevance_score=ref.get("score", 0.0)
            )

            all_snippets.append(snippet)
            pack.snippets.append(snippet)

            # Pack 요약 필드 채우기
            if snippet.claim_type == ClaimType.MODEL:
                pack.model_used = extract_model_name(snippet.text)
            elif snippet.claim_type == ClaimType.PERTURBATION:
                pack.perturbation_used = extract_perturbation(snippet.text)
            # ...

        all_packs.append(pack)

    # claim_type별 요약 생성
    summary = build_evidence_summary(all_snippets)

    return {
        "evidence_snippets": all_snippets,
        "evidence_packs": all_packs,
        "evidence_summary": summary
    }

def classify_claim_type(text: str) -> ClaimType:
    """텍스트에서 claim_type 분류"""
    text_lower = text.lower()

    if any(kw in text_lower for kw in ["cell line", "pdx", "xenograft", "mouse", "patient"]):
        return ClaimType.MODEL
    elif any(kw in text_lower for kw in ["knockdown", "sirna", "crispr", "inhibitor", "treated"]):
        return ClaimType.PERTURBATION
    elif any(kw in text_lower for kw in ["western", "elisa", "viability", "apoptosis", "measured"]):
        return ClaimType.READOUT
    elif any(kw in text_lower for kw in ["limitation", "caveat", "however", "although"]):
        return ClaimType.LIMITATION
    else:
        return ClaimType.RESULT
```

---

### 4.4 Node 8: critique_and_refine (Critic 루프)

**Critic 체크리스트 (확장)**:

1. **대조군 완비성**
   - [ ] Negative control (무처치)
   - [ ] Vehicle control (DMSO 등)
   - [ ] Positive control (알려진 효과)
   - [ ] Non-targeting control (siRNA-NC)
   - [ ] Rescue control (과발현으로 복구)

2. **해석 모호성**
   - [ ] 결과가 여러 가설을 동시에 만족시키는가?

3. **교란변수**
   - [ ] 통제되지 않은 변수가 있는가?

4. **구분력 (Discriminative Power)**
   - [ ] sample size가 예상 effect size 검출에 충분한가?
   - [ ] 이 결과가 test_question을 실제로 판별하는가?

5. **측정치-가설 정렬**
   - [ ] primary endpoint가 hypothesis_tested를 직접 때리는가?

```python
CRITIQUE_SYSTEM = """You are a rigorous scientific reviewer.
Critique experimental designs BEFORE experiments are run.

## Critique Checklist (Extended)

### 1. Control Group Completeness
Check for ALL required controls:
- [ ] Negative control (untreated)
- [ ] Vehicle control (DMSO/saline if applicable)
- [ ] Positive control (known effect)
- [ ] Non-targeting control (siRNA-NC for knockdown)
- [ ] Rescue control (overexpression to restore phenotype)

### 2. Interpretation Ambiguity
- [ ] Could the result support multiple conflicting hypotheses?
- [ ] Is there a unique interpretation of the expected result?

### 3. Confounders
- [ ] Are there uncontrolled variables that could explain the result?
- [ ] Cell passage number, culture conditions, batch effects?

### 4. Discriminative Power
- [ ] Is sample size sufficient to detect the expected effect size?
- [ ] Does this experiment actually answer the test_question?
- [ ] Could both "true" and "false" outcomes lead to the same result?

### 5. Endpoint-Hypothesis Alignment
- [ ] Does primary endpoint DIRECTLY test the hypothesis?
- [ ] Are pathway markers included to confirm mechanism (not just phenotype)?

## Output Format (JSON)

{
  "quality_score": 0.65,
  "passed": false,
  "critique_report": {
    "missing_controls": ["vehicle", "rescue"],
    "ambiguity_issues": ["IC50 change alone doesn't confirm MET dependency"],
    "confounders": ["Cell line batch variation"],
    "discriminative_power_issues": ["n=3 insufficient for 20% difference"],
    "endpoint_alignment_issues": ["Add pMET/pAKT to confirm on-target effect"],
    "feasibility_conflicts": []
  },
  "revision_suggestions": [
    "Add DMSO vehicle control to all drug treatment groups",
    "Add MET overexpression rescue experiment",
    "Include pMET/pAKT western blot as secondary endpoint",
    "Increase n to 6 per group"
  ]
}
"""
```

---

### 4.5 Node 11: approval_gate (승인 게이트)

**승인 필요 조건**:
- `estimated_cost_level == HIGH or VERY_HIGH`
- `in_vivo` 포함 → IACUC 필요
- 임상 데이터/IRB 필요
- 오믹스 분석 포함

**선택지 제공**:

```python
async def approval_gate_node(state: StudyPlanState) -> dict:
    """승인 게이트 - 선택지와 함께 승인 요청"""

    designs = state["experiment_designs"]
    feasibility = state["feasibility"]

    approval_items = []
    choices = []

    # 승인 필요 항목 수집
    for design in designs:
        if design.experiment_type == ExperimentType.IN_VIVO:
            approval_items.append(ApprovalItem(
                item_type="in_vivo",
                reason="IACUC 승인 필요",
                cost_bucket=design.estimated_cost_level,
                ethics_bucket=EthicsBucket.IACUC
            ))

        if design.estimated_cost_level in [CostBucket.HIGH, CostBucket.VERY_HIGH]:
            approval_items.append(ApprovalItem(
                item_type="high_cost",
                reason=f"예상 비용 {design.estimated_cost_level.value}",
                cost_bucket=design.estimated_cost_level
            ))

    # 승인 필요한 경우 선택지 생성
    if approval_items:
        choices = [
            ApprovalChoice(
                choice_id="approve_all",
                label="전체 승인하고 진행",
                description="모든 실험 포함",
                estimated_cost="$80K",
                estimated_timeline="6개월"
            ),
            ApprovalChoice(
                choice_id="in_vitro_only",
                label="In vitro만으로 1차 검증",
                description="동물실험 제외",
                estimated_cost="$15K",
                estimated_timeline="2개월"
            ),
            ApprovalChoice(
                choice_id="reduce_scope",
                label="범위 축소 (오믹스 제외)",
                description="RNA-seq 제외한 저비용 플랜",
                estimated_cost="$30K",
                estimated_timeline="3개월"
            )
        ]

    approval_required = len(approval_items) > 0
    status = ApprovalStatus.NEEDS_USER if approval_required else ApprovalStatus.APPROVED

    return {
        "approval_gate_result": ApprovalGateResult(
            approval_required=approval_required,
            approval_items=approval_items,
            choices=choices,
            approval_status=status
        ),
        "approval_status": status,
        "approval_log": state.get("approval_log", []) + [{
            "timestamp": datetime.now().isoformat(),
            "items": [asdict(i) for i in approval_items],
            "status": status.value
        }]
    }
```

---

## 5. SSE 이벤트 v2.1

### 5.1 이벤트 타입 (확장)

```python
class StudyPlanEventType(str, Enum):
    STATUS = "status"
    HYPOTHESIS_PARSED = "hypothesis"
    TESTS_DECOMPOSED = "tests"              # 검증 질문 리스트
    STUDIES_FOUND = "studies"
    SEARCH_EXPANDING = "search_expanding"   # 검색 확장 중
    EVIDENCE_PACKED = "evidence"            # Evidence Pack 완료
    METHODOLOGY_ANALYZED = "methodology"
    EXPERIMENTS_DESIGNED = "experiments"
    CRITIQUE = "critique"                   # Critic 결과
    REVISION = "revision"                   # 수정 진행 중
    MEASUREMENTS_IDENTIFIED = "measurements"
    FEASIBILITY_ASSESSED = "feasibility"
    APPROVAL_REQUIRED = "approval_required" # 선택지 포함
    TOKEN = "token"
    RESULT = "result"
    ERROR = "error"
    DONE = "done"
```

### 5.2 이벤트 예시

```json
// 검색 확장 중
{
  "event": "search_expanding",
  "data": {
    "current_coverage": 0.45,
    "expand_count": 1,
    "new_queries": ["MET inhibitor NSCLC clinical trial", "MET-EGFR combination therapy"]
  }
}

// Evidence Pack 완료
{
  "event": "evidence",
  "data": {
    "total_snippets": 45,
    "by_claim_type": {
      "model": 12,
      "perturbation": 15,
      "readout": 10,
      "result": 8
    },
    "papers_count": 15
  }
}

// Critic 결과
{
  "event": "critique",
  "data": {
    "quality_score": 0.65,
    "passed": false,
    "missing_controls": ["vehicle", "rescue"],
    "revision_suggestions": [
      "Add DMSO vehicle control",
      "Include rescue experiment"
    ]
  }
}

// 수정 진행
{
  "event": "revision",
  "data": {
    "revision_count": 1,
    "changes": ["Added vehicle control", "Added pMET western blot"],
    "quality_before": 0.65,
    "quality_after": 0.82
  }
}

// 승인 필요 (선택지 포함)
{
  "event": "approval_required",
  "data": {
    "items": [
      {"type": "in_vivo", "reason": "IACUC 필요", "cost_bucket": "high"},
      {"type": "high_cost", "reason": "예상 비용 $80K"}
    ],
    "choices": [
      {
        "choice_id": "approve_all",
        "label": "전체 승인하고 진행",
        "estimated_cost": "$80K",
        "estimated_timeline": "6개월"
      },
      {
        "choice_id": "in_vitro_only",
        "label": "In vitro만으로 1차 검증",
        "estimated_cost": "$15K",
        "estimated_timeline": "2개월"
      }
    ]
  }
}
```

---

## 6. 데이터 모델 (DB)

### 6.1 study_plans 테이블 v2.1

```sql
CREATE TABLE study_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 관계
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,

    -- 입력
    hypothesis_input TEXT NOT NULL,
    research_context TEXT,
    constraints JSONB DEFAULT '[]',
    preferred_experiment_types TEXT[] DEFAULT '{}',

    -- 파싱된 가설
    hypothesis_structured JSONB,
    hypothesis_confidence FLOAT,

    -- 검증 질문
    test_questions JSONB DEFAULT '[]',

    -- 검색 결과
    search_queries TEXT[],
    search_coverage_score FLOAT,
    search_gap_notes TEXT[],
    search_expand_count INTEGER DEFAULT 0,
    prior_studies_count INTEGER DEFAULT 0,

    -- Evidence Pack (별도 저장)
    evidence_snippets JSONB DEFAULT '[]',
    evidence_packs JSONB DEFAULT '[]',
    evidence_summary JSONB,

    -- 방법론 분석
    methodology_patterns JSONB DEFAULT '[]',
    common_biomarkers JSONB DEFAULT '[]',

    -- 실험 설계
    experiment_designs JSONB DEFAULT '[]',

    -- Critique 결과
    critique_result JSONB,
    quality_score FLOAT,
    revision_count INTEGER DEFAULT 0,
    revision_history JSONB DEFAULT '[]',

    -- 측정치
    measurements JSONB DEFAULT '[]',

    -- 실현가능성
    feasibility_assessment JSONB,

    -- 승인 게이트
    approval_required BOOLEAN DEFAULT FALSE,
    approval_items JSONB DEFAULT '[]',
    approval_choices JSONB DEFAULT '[]',
    approval_status VARCHAR(20) DEFAULT 'approved',
    user_decision JSONB,
    approval_log JSONB DEFAULT '[]',

    -- 최종 결과
    final_plan TEXT,
    executive_summary TEXT,
    evidence_trace JSONB DEFAULT '{}',

    -- 메타데이터
    status VARCHAR(30) DEFAULT 'processing',
    status_detail TEXT,
    total_duration_ms INTEGER,
    error_message TEXT,

    -- 운영/추적
    run_version VARCHAR(50),
    model_versions JSONB DEFAULT '{}',
    token_usage JSONB DEFAULT '{}',
    cost_estimate FLOAT,
    user_feedback VARCHAR(20),
    user_feedback_reason TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_study_plans_user_id ON study_plans(user_id);
CREATE INDEX idx_study_plans_status ON study_plans(status);
CREATE INDEX idx_study_plans_approval ON study_plans(approval_required, approval_status);
CREATE INDEX idx_study_plans_created_at ON study_plans(created_at DESC);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_study_plans_updated_at
    BEFORE UPDATE ON study_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

## 7. 구현 우선순위 v2.1

### Sprint 1: Core Agentic Features (2주)

| 태스크 | 설명 | 우선순위 |
|--------|------|---------|
| `decompose_to_test_questions` | + decision_rule | P0 |
| `expand_search` | 검색 커버리지 루프 | P0 |
| `build_evidence_pack` | claim_type별 분리 | P0 |
| `critique_and_refine` | 확장된 체크리스트 + revision_history | P0 |
| `approval_gate` | choices 포함 | P0 |

### Sprint 2: Evidence & Tracking (1주)

| 태스크 | 설명 | 우선순위 |
|--------|------|---------|
| Evidence Snippet 오프셋 추출 | RAG 결과에 오프셋 | P1 |
| Evidence Trace | 최종 결과 ↔ 스니펫 매핑 | P1 |
| approval_log | 승인 이력 저장 | P1 |
| revision_history | 수정 이력 저장 | P1 |

### Sprint 3: Polish & Testing (1주)

| 태스크 | 설명 | 우선순위 |
|--------|------|---------|
| SSE 이벤트 확장 | EVIDENCE_PACKED, REVISION | P2 |
| 프롬프트 튜닝 | 도메인 전문가 피드백 | P2 |
| E2E 테스트 | 전체 루프 테스트 | P2 |

---

## 8. v1.0 vs v2.0 vs v2.1 비교

| 항목 | v1.0 | v2.0 | v2.1 |
|------|------|------|------|
| **노드 수** | 7 | 9 | 12 |
| **검색 루프** | ❌ | ❌ | ✅ expand_search |
| **Evidence Pack** | ❌ | 검색 내부 | ✅ 별도 노드 |
| **decision_rule** | ❌ | expected_outcome | ✅ 간결한 rule |
| **search_coverage** | str | str | ✅ float + gap_notes |
| **Critic 대조군** | 4종 | 4종 | ✅ 5종 (rescue 포함) |
| **revision_history** | ❌ | ❌ | ✅ |
| **approval choices** | ❌ | 기본 | ✅ 선택지 제공 |
| **approval_log** | ❌ | ❌ | ✅ |
| **SSE 이벤트** | 기본 | 확장 | ✅ REVISION 등 |

---

## Appendix A: 용어 정의

| 용어 | 정의 |
|------|------|
| Necessity Test | X를 제거했을 때 phenotype이 사라지는지 확인 |
| Sufficiency Test | X를 추가했을 때 phenotype이 발생하는지 확인 |
| Epistasis | 신호전달 경로에서 X와 Y의 상하위 관계 |
| Specificity | off-target 효과 없이 특정 조건에서만 효과 발생 |
| decision_rule | 어떤 결과면 가설을 지지/반박하는지 명시 |
| Evidence Snippet | 논문의 특정 위치(오프셋)에서 추출한 근거 텍스트 |
| Evidence Pack | 논문별로 묶인 Evidence Snippet 컬렉션 |
| claim_type | model/perturbation/readout/result/limitation |
| Critique | 실험 설계의 논리적 허점을 자가 검증 |
| Approval Gate | 비용/윤리적 이유로 사용자 승인이 필요한 단계 |
| revision_history | 무엇을 왜 바꿨는지 기록 |

---

## Appendix B: Changelog

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2025-01-21 | 초기 설계 (7노드 순차) |
| 2.0 | 2025-01-21 | Agentic 기능 추가 (Critic, 승인게이트, Evidence Pack) |
| 2.1 | 2025-01-21 | 통합 최적화 (검색루프, decision_rule, choices, revision_history) |

---

*Last Updated: 2025-01-21*
