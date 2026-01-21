"""Study Plan Agent 모듈

가설 기반 실험 설계 에이전트.

주요 Export:
- StudyPlanService: 에이전트 서비스 (싱글톤)
- study_plan_service: 서비스 인스턴스
- get_study_plan_service: 의존성 주입 함수
- StudyPlanState: 에이전트 상태
- StudyPlanEvent: SSE 이벤트
- StudyPlanResult: 실행 결과
- StudyPlanEventType: 이벤트 타입 Enum
"""

from .service import (
    StudyPlanEvent,
    StudyPlanEventType,
    StudyPlanResult,
    StudyPlanService,
    get_study_plan_service,
    study_plan_service,
)
from .state import (
    ApprovalChoice,
    ApprovalGateResult,
    ApprovalItem,
    ApprovalStatus,
    ClaimType,
    ControlGroup,
    ControlType,
    CostBucket,
    CritiqueReport,
    CritiqueResult,
    EthicsBucket,
    EvidenceLevel,
    EvidencePack,
    EvidenceSnippet,
    EvidenceSummaryByClaim,
    ExperimentDesign,
    ExperimentType,
    FeasibilityAssessment,
    HypothesisStructure,
    MeasurementItem,
    MethodologyPattern,
    RevisionRecord,
    StudyPlanState,
    TestCategory,
    TestQuestion,
    create_initial_state,
)

__all__ = [
    # Service
    "StudyPlanService",
    "study_plan_service",
    "get_study_plan_service",
    # Events
    "StudyPlanEvent",
    "StudyPlanEventType",
    "StudyPlanResult",
    # State
    "StudyPlanState",
    "create_initial_state",
    # Enums
    "TestCategory",
    "ClaimType",
    "ExperimentType",
    "EvidenceLevel",
    "CostBucket",
    "EthicsBucket",
    "ApprovalStatus",
    "ControlType",
    # Dataclasses
    "HypothesisStructure",
    "TestQuestion",
    "EvidenceSnippet",
    "EvidencePack",
    "EvidenceSummaryByClaim",
    "ControlGroup",
    "ExperimentDesign",
    "CritiqueReport",
    "CritiqueResult",
    "RevisionRecord",
    "ApprovalItem",
    "ApprovalChoice",
    "ApprovalGateResult",
    "MeasurementItem",
    "FeasibilityAssessment",
    "MethodologyPattern",
]
