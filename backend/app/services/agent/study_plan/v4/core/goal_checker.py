"""Goal checker component for v4 agent.

The GoalChecker is responsible for:
1. Evaluating if the goal has been achieved
2. Checking minimum requirements
3. Providing detailed status on each requirement
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.services.agent.study_plan.v4.core.state import WorkingMemory

logger = logging.getLogger(__name__)


@dataclass
class GoalStatus:
    """Status of goal achievement."""

    achieved: bool
    details: dict[str, bool]
    missing: list[str]
    quality_assessment: str


class GoalChecker:
    """Checks if the research plan generation goal is achieved.

    Validates multiple requirements:
    - Hypothesis parsed
    - Test questions generated
    - Experiments designed
    - Controls complete
    - Measurements coverage
    - Quality score
    """

    # Minimum requirements for goal achievement
    MINIMUM_REQUIREMENTS = {
        "hypothesis_parsed": True,
        "test_questions_count": 3,
        "experiments_count": 1,
        "quality_score": 0.7,
        "controls_complete": True,
        "measurements_coverage": 0.8,
    }

    def __init__(
        self,
        min_test_questions: int = 3,
        min_experiments: int = 1,
        min_quality_score: float = 0.7,
        min_measurements_coverage: float = 0.8,
    ):
        """Initialize with customizable thresholds.

        Args:
            min_test_questions: Minimum number of test questions
            min_experiments: Minimum number of experiments
            min_quality_score: Minimum quality score (0-1)
            min_measurements_coverage: Minimum coverage of hypothesis variables
        """
        self.min_test_questions = min_test_questions
        self.min_experiments = min_experiments
        self.min_quality_score = min_quality_score
        self.min_measurements_coverage = min_measurements_coverage

    def check(self, state: WorkingMemory) -> GoalStatus:
        """Check if goal is achieved based on current state.

        Args:
            state: Current working memory

        Returns:
            GoalStatus with achievement status and details
        """
        details = {
            "hypothesis_parsed": self._check_hypothesis_parsed(state),
            "test_questions_sufficient": self._check_test_questions(state),
            "experiments_designed": self._check_experiments(state),
            "controls_complete": self._check_controls(state),
            "measurements_coverage": self._check_measurements_coverage(state),
            "quality_score_met": self._check_quality_score(state),
        }

        missing = [name for name, passed in details.items() if not passed]
        achieved = len(missing) == 0

        quality_assessment = self._generate_quality_assessment(state, details)

        if achieved:
            logger.info("Goal achieved - all requirements met")
        else:
            logger.info(f"Goal not achieved - missing: {missing}")

        return GoalStatus(
            achieved=achieved,
            details=details,
            missing=missing,
            quality_assessment=quality_assessment,
        )

    def _check_hypothesis_parsed(self, state: WorkingMemory) -> bool:
        """Check if hypothesis has been parsed."""
        return state.structured_hypothesis is not None

    def _check_test_questions(self, state: WorkingMemory) -> bool:
        """Check if sufficient test questions have been generated."""
        return len(state.test_questions) >= self.min_test_questions

    def _check_experiments(self, state: WorkingMemory) -> bool:
        """Check if sufficient experiments have been designed."""
        return len(state.experiments) >= self.min_experiments

    def _check_controls(self, state: WorkingMemory) -> bool:
        """Check if each experiment has required controls.

        Required controls:
        - Vehicle/negative control
        - Positive control
        """
        if not state.experiments:
            return False

        for exp in state.experiments:
            exp_id = exp.get("id") or exp.get("name", str(hash(str(exp))))
            controls = state.controls.get(exp_id, [])

            # Check for vehicle/negative control
            has_vehicle = any(
                c.get("type") in ("vehicle", "negative") for c in controls
            )

            # Check for positive control
            has_positive = any(c.get("type") == "positive" for c in controls)

            if not (has_vehicle and has_positive):
                logger.debug(
                    f"Experiment {exp_id} missing controls: "
                    f"vehicle={has_vehicle}, positive={has_positive}"
                )
                return False

        return True

    def _check_measurements_coverage(self, state: WorkingMemory) -> bool:
        """Check if measurements cover hypothesis variables."""
        if not state.structured_hypothesis:
            return False

        # Get required variables from hypothesis
        required_vars = state.get_hypothesis_variables()
        if not required_vars:
            # If no variables identified, consider it covered
            return True

        # Get measured variables
        measured_vars = set()
        for m in state.measurements:
            if target := m.get("target"):
                measured_vars.add(target.lower())
            if targets := m.get("targets"):
                measured_vars.update(t.lower() for t in targets)

        # Normalize for comparison
        required_lower = {v.lower() for v in required_vars}

        # Calculate coverage
        if not required_lower:
            return True

        covered = len(required_lower & measured_vars)
        coverage = covered / len(required_lower)

        logger.debug(
            f"Measurements coverage: {coverage:.0%} "
            f"(required: {required_lower}, measured: {measured_vars})"
        )

        return coverage >= self.min_measurements_coverage

    def _check_quality_score(self, state: WorkingMemory) -> bool:
        """Check if quality score meets minimum."""
        return state.quality_score >= self.min_quality_score

    def _generate_quality_assessment(
        self,
        state: WorkingMemory,
        details: dict[str, bool],
    ) -> str:
        """Generate a human-readable quality assessment."""
        passed = sum(1 for v in details.values() if v)
        total = len(details)

        lines = [
            f"Quality Assessment: {passed}/{total} requirements met",
            "",
        ]

        # Add details for each check
        status_map = {True: "PASS", False: "FAIL"}

        for check_name, passed in details.items():
            status = status_map[passed]
            lines.append(f"  [{status}] {check_name.replace('_', ' ').title()}")

        # Add specific metrics
        lines.extend([
            "",
            "Metrics:",
            f"  - Test questions: {len(state.test_questions)}",
            f"  - Experiments: {len(state.experiments)}",
            f"  - Quality score: {state.quality_score:.0%}",
            f"  - Iterations: {state.iteration_count}",
        ])

        return "\n".join(lines)

    def get_next_priority(self, state: WorkingMemory) -> str | None:
        """Get the highest priority missing requirement.

        Useful for guiding the agent on what to work on next.

        Returns:
            Name of the highest priority missing requirement, or None if complete
        """
        status = self.check(state)

        if status.achieved:
            return None

        # Priority order
        priority = [
            "hypothesis_parsed",
            "test_questions_sufficient",
            "experiments_designed",
            "controls_complete",
            "measurements_coverage",
            "quality_score_met",
        ]

        for requirement in priority:
            if not status.details.get(requirement, True):
                return requirement

        return status.missing[0] if status.missing else None
