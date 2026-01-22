"""Study Plan Agent 상태 정의 (v3)

가설 기반 실험 설계 에이전트의 상태, 열거형, 데이터클래스 정의.

v3 변경사항:
- 3-tier 검색 (RAG → EPMC → Web) 지원
- Decision Point 결과 추적 (DP1, DP2, DP3)
- Plan A/B 구조 지원
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict


# ============================================================
# Enums
# ============================================================


class TestCategory(str, Enum):
    """검증 질문 카테고리 (NSPE)"""

    NECESSITY = "necessity"  # X 막으면 phenotype 사라지나?
    SUFFICIENCY = "sufficiency"  # X 올리면 phenotype 생기나?
    EPISTASIS = "epistasis"  # X가 Y 위/아래? (directionality)
    SPECIFICITY = "specificity"  # off-target / 다른 세포타입 재현?


class ClaimType(str, Enum):
    """Evidence Snippet의 주장 유형"""

    MODEL = "model"  # 어떤 모델을 썼는지
    PERTURBATION = "perturbation"  # 어떤 perturbation을 썼는지
    READOUT = "readout"  # 어떤 readout을 봤는지
    RESULT = "result"  # 결과/결론
    LIMITATION = "limitation"  # 한계점


class ExperimentType(str, Enum):
    """실험 유형"""

    IN_VITRO = "in_vitro"
    IN_VIVO = "in_vivo"
    CLINICAL = "clinical"
    COMPUTATIONAL = "computational"


class EvidenceLevel(str, Enum):
    """근거 수준"""

    HIGH = "high"  # RCT, Meta-analysis
    MODERATE = "moderate"  # Cohort, Case-control
    LOW = "low"  # Case series, Expert opinion
    PRECLINICAL = "preclinical"


class CostBucket(str, Enum):
    """비용 수준"""

    LOW = "low"  # < $10K
    MEDIUM = "medium"  # $10K - $50K
    HIGH = "high"  # $50K - $200K
    VERY_HIGH = "very_high"  # > $200K


class EthicsBucket(str, Enum):
    """윤리 심의 수준"""

    NONE = "none"
    IACUC = "iacuc"  # 동물실험위원회
    IRB_EXPEDITED = "irb_expedited"
    IRB_FULL = "irb_full"


class ApprovalStatus(str, Enum):
    """승인 상태"""

    APPROVED = "approved"
    NEEDS_USER = "needs_user"
    REJECTED = "rejected"


class ControlType(str, Enum):
    """대조군 유형"""

    NEGATIVE = "negative"  # 무처치
    VEHICLE = "vehicle"  # DMSO 등
    POSITIVE = "positive"  # 알려진 효과
    NON_TARGETING = "non_targeting"  # siRNA-NC
    RESCUE = "rescue"  # 과발현 복구


# ============================================================
# Dataclasses - 가설 관련
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
    question: str  # "MET을 억제하면 osimertinib 민감성이 회복되는가?"
    rationale: str  # 왜 이 질문이 중요한가
    decision_rule: str  # "IC50 50% 감소 시 가설 지지, 변화 없으면 반박"
    suggested_approach: str  # 검증 접근법 제안
    priority: int = 1  # 1=필수, 2=권장, 3=선택


# ============================================================
# Dataclasses - Evidence 관련
# ============================================================


@dataclass
class EvidenceSnippet:
    """근거 스니펫 - 정확한 출처 추적"""

    snippet_id: str  # 고유 ID
    paper_id: str  # "pmid:12345678"
    section: str  # "methods", "results"
    offset_start: int  # UTF-8 문자 위치
    offset_end: int
    claim_type: ClaimType  # model/perturbation/readout/result/limitation
    text: str  # 실제 텍스트 (짧게, 저작권 고려)
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

    models: list[dict] = field(default_factory=list)  # [{paper_id, model, snippet_id}]
    perturbations: list[dict] = field(default_factory=list)
    readouts: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    limitations: list[dict] = field(default_factory=list)


# ============================================================
# Dataclasses - 실험 설계 관련
# ============================================================


@dataclass
class ControlGroup:
    """대조군 정의"""

    control_type: ControlType
    name: str
    description: str
    n: int = 6  # 샘플 수


@dataclass
class ExperimentDesign:
    """실험 설계 초안"""

    experiment_id: str  # "exp_1_in_vitro"
    experiment_type: ExperimentType
    title: str
    objective: str
    hypothesis_tested: str
    test_category: TestCategory  # 어떤 검증 질문을 테스트하는지

    # 실험 그룹
    experimental_groups: list[dict] = field(default_factory=list)
    control_groups: list[ControlGroup] = field(default_factory=list)

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
# Dataclasses - Critique 관련
# ============================================================


@dataclass
class CritiqueReport:
    """Critic 상세 보고서"""

    # 대조군 검사 (5종)
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

    quality_score: float  # 0-1 (0.8 이상이면 pass)
    critique_report: CritiqueReport
    revision_suggestions: list[str] = field(default_factory=list)
    passed: bool = False


@dataclass
class RevisionRecord:
    """수정 이력"""

    revision_number: int
    changes_made: list[str]  # 무엇을 바꿨는지
    reason: str  # 왜 바꿨는지
    quality_before: float
    quality_after: float


# ============================================================
# Dataclasses - 승인 게이트 관련
# ============================================================


@dataclass
class ApprovalItem:
    """승인 필요 항목"""

    item_type: str  # "in_vivo", "omics", "clinical_data", "high_cost"
    reason: str  # "IACUC 필요", "RNA-seq 예산/분석 필요"
    cost_bucket: CostBucket
    ethics_bucket: EthicsBucket = EthicsBucket.NONE


@dataclass
class ApprovalChoice:
    """사용자에게 제공할 선택지"""

    choice_id: str  # "approve_all", "reduce_scope", "alternative"
    label: str  # "승인하고 진행"
    description: str  # "예상 비용 $80K, 기간 6개월"
    estimated_cost: str
    estimated_timeline: str


@dataclass
class ApprovalGateResult:
    """승인 게이트 결과"""

    approval_required: bool
    approval_items: list[ApprovalItem] = field(default_factory=list)
    choices: list[ApprovalChoice] = field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    user_decision: dict | None = None  # 사용자 선택 결과


# ============================================================
# Dataclasses - 측정 및 실현가능성 관련
# ============================================================


@dataclass
class MeasurementItem:
    """측정 항목"""

    category: str  # "biomarker", "clinical", "molecular"
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

    # 기본값 없는 필드들 먼저
    overall_score: float
    technical_feasibility: float
    resource_feasibility: float
    timeline_feasibility: float
    # 기본값 있는 필드들
    technical_concerns: list[str] = field(default_factory=list)
    resource_concerns: list[str] = field(default_factory=list)
    timeline_concerns: list[str] = field(default_factory=list)
    ethical_considerations: list[str] = field(default_factory=list)
    alternative_approaches: list[str] = field(default_factory=list)
    risk_mitigation: list[str] = field(default_factory=list)


@dataclass
class MethodologyPattern:
    """방법론 패턴"""

    pattern_name: str
    frequency: int  # 몇 개 논문에서 사용
    papers: list[str] = field(default_factory=list)
    description: str = ""


# ============================================================
# Main State
# ============================================================


class StudyPlanState(TypedDict, total=False):
    """Study Plan Agent 상태 v3

    v2.1 호환성 유지하면서 v3 기능 추가
    """

    # === v3 실행 ID ===
    run_id: str  # 실행 고유 ID (예산 추적용)

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
    prior_studies: list[dict]  # 간단한 메타데이터
    search_coverage_score: float  # 0-1 (0.6 미만이면 확장)
    search_gap_notes: list[str]  # 커버리지 부족 영역
    search_expand_count: int  # 확장 횟수

    # === v3: Multi-Tier Search ===
    search_tier_history: list[int]  # [1, 2] = RAG → EPMC
    evidence_snippets_v3: list[dict]  # EvidenceSnippetV3.to_dict() 목록
    current_tier: int  # 1=RAG, 2=EPMC, 3=WEB
    run_epmc_count: int  # run당 EPMC 호출 횟수
    run_web_count: int  # run당 Web 호출 횟수
    dp1_decisions: list[dict]  # DP1RouterOutput.to_dict() 이력

    # === Node 4: expand_search ===
    expanded_queries: list[str]

    # === Node 5: build_evidence_pack ===
    evidence_snippets: list[EvidenceSnippet]
    evidence_packs: list[EvidencePack]
    evidence_summary: EvidenceSummaryByClaim | None

    # === Node 6: analyze_methodologies ===
    methodology_patterns: list[MethodologyPattern]
    common_biomarkers: list[str]
    common_techniques: list[str]
    methodology_gaps: list[str]

    # === Node 7: design_experiments ===
    experiment_designs: list[ExperimentDesign]
    design_rationale: str

    # === Node 8: critique_and_refine ===
    critique_result: CritiqueResult | None
    quality_score: float  # 편의 필드
    revision_count: int
    revision_history: list[RevisionRecord]

    # === v3: DP2 Critique 결과 ===
    dp2_decision: str  # "redesign", "search_for_controls", "ask_user", "accept_minor_issues"
    dp2_loop_count: int  # DP2 루프 횟수 (최대 2)
    previous_gaps_searched: list[str]  # 같은 gap 연속 검색 금지용

    # === Node 9: identify_measurements ===
    measurements: list[MeasurementItem]
    measurement_priority: list[str]

    # === Node 10: validate_feasibility ===
    feasibility: FeasibilityAssessment | None

    # === Node 11: approval_gate ===
    approval_gate_result: ApprovalGateResult | None
    approval_status: ApprovalStatus
    approval_log: list[dict]  # 승인 요청/응답 기록

    # === Node 12: synthesize_plan ===
    final_plan: str
    executive_summary: str
    references: list[dict]
    evidence_trace: dict  # {문장/섹션 ID: [snippet_id, ...]}

    # === v3: Plan A/B 구조 ===
    dp3_decision: str  # "single_plan", "plan_a_b", "plan_b_only"
    plan_a: str  # 이상적 실험 설계
    plan_b: str  # 현실적 대안
    plan_config: dict  # DP3 설정 (focus, constraint 등)
    web_limit_exceeded: bool  # Web 검색 예산 초과 여부

    # === 메타데이터 ===
    conversation_id: str | None
    user_id: str | None
    created_at: str
    total_duration_ms: int
    error: str | None

    # === 운영/추적 필드 ===
    run_version: str
    model_versions: dict[str, str]  # {"parse": "gpt-4o", "critique": "gpt-4o"}
    token_usage: dict[str, int]  # {"prompt": 5000, "completion": 3000}
    cost_estimate: float
    status_detail: str


# ============================================================
# Helper Functions
# ============================================================


def create_initial_state(
    user_input: str,
    research_context: str | None = None,
    constraints: list[str] | None = None,
    preferred_experiment_types: list[ExperimentType] | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> StudyPlanState:
    """초기 상태 생성 (v3)"""
    from datetime import datetime
    import uuid

    return StudyPlanState(
        # v3 실행 ID
        run_id=run_id or str(uuid.uuid4()),
        # 입력
        user_input=user_input,
        research_context=research_context,
        constraints=constraints or [],
        preferred_experiment_types=preferred_experiment_types or [],
        # 초기화
        hypothesis=None,
        hypothesis_confidence=0.0,
        clarification_needed=False,
        clarification_questions=[],
        user_clarification=None,
        test_questions=[],
        search_queries=[],
        prior_studies=[],
        search_coverage_score=0.0,
        search_gap_notes=[],
        search_expand_count=0,
        expanded_queries=[],
        evidence_snippets=[],
        evidence_packs=[],
        evidence_summary=None,
        methodology_patterns=[],
        common_biomarkers=[],
        common_techniques=[],
        methodology_gaps=[],
        experiment_designs=[],
        design_rationale="",
        critique_result=None,
        quality_score=0.0,
        revision_count=0,
        revision_history=[],
        measurements=[],
        measurement_priority=[],
        feasibility=None,
        approval_gate_result=None,
        approval_status=ApprovalStatus.APPROVED,
        approval_log=[],
        final_plan="",
        executive_summary="",
        references=[],
        evidence_trace={},
        # v3: Multi-Tier Search
        search_tier_history=[],
        evidence_snippets_v3=[],
        current_tier=1,  # RAG
        run_epmc_count=0,
        run_web_count=0,
        dp1_decisions=[],
        # v3: DP2 Critique
        dp2_decision="",
        dp2_loop_count=0,
        previous_gaps_searched=[],
        # v3: Plan A/B
        dp3_decision="",
        plan_a="",
        plan_b="",
        plan_config={},
        web_limit_exceeded=False,
        # 메타
        conversation_id=conversation_id,
        user_id=user_id,
        created_at=datetime.now().isoformat(),
        total_duration_ms=0,
        error=None,
        # 운영
        run_version="v3",
        model_versions={},
        token_usage={"prompt": 0, "completion": 0},
        cost_estimate=0.0,
        status_detail="initialized",
    )
