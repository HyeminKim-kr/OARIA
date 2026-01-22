"""Core type definitions for v4 agent."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    """Agent action types."""

    # Search actions
    SEARCH_RAG = "search_rag"
    SEARCH_EPMC = "search_epmc"
    SEARCH_WEB = "search_web"

    # Analysis actions
    PARSE_HYPOTHESIS = "parse_hypothesis"
    DECOMPOSE_QUESTIONS = "decompose_questions"
    ANALYZE_METHODOLOGY = "analyze_methodology"

    # Design actions
    DESIGN_EXPERIMENT = "design_experiment"
    DESIGN_CONTROLS = "design_controls"
    SUGGEST_MEASUREMENTS = "suggest_measurements"

    # Validation actions
    VALIDATE_CONTROLS = "validate_controls"
    VALIDATE_COVERAGE = "validate_coverage"
    CRITIQUE_DESIGN = "critique_design"

    # Synthesis actions
    SYNTHESIZE_PLAN = "synthesize_plan"
    GENERATE_PLAN_B = "generate_plan_b"

    # User interaction
    ASK_USER = "ask_user"

    # Memory actions
    RECALL_SIMILAR = "recall_similar"
    STORE_RESULT = "store_result"

    # Terminal
    FINISH = "FINISH"


@dataclass
class Action:
    """Agent action to execute."""

    name: str
    input: dict[str, Any]
    confidence: float = 0.5
    alternative: str | None = None


@dataclass
class Observation:
    """Result of executing an action."""

    success: bool
    result: Any = None
    error: str | None = None
    is_terminal: bool = False
    duration_ms: int = 0
    cost: float = 0.0


@dataclass
class RecoveryPlan:
    """Plan for recovering from failure."""

    strategy: str
    next_actions: list[Action] = field(default_factory=list)
    message: str | None = None
    options: list[str] = field(default_factory=list)


@dataclass
class AgentResult:
    """Final result of agent execution."""

    success: bool
    plan_a: str | None = None
    plan_b: str | None = None
    executive_summary: str | None = None
    experiment_count: int = 0
    quality_score: float = 0.0
    iteration_count: int = 0
    total_duration_ms: int = 0
    error: str | None = None

    # Detailed results
    experiments: list[dict[str, Any]] = field(default_factory=list)
    evidence_snippets: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[dict[str, Any]] = field(default_factory=list)
    validation_results: list[dict[str, Any]] = field(default_factory=list)

    # Execution trace
    execution_trace: list[dict[str, Any]] = field(default_factory=list)
