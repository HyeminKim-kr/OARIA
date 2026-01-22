"""Validate coverage tool."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class ValidateCoverageTool(BaseTool):
    """Validate measurement coverage of hypothesis variables.

    Ensures all important variables are measured.
    """

    @property
    def name(self) -> str:
        return "validate_coverage"

    @property
    def description(self) -> str:
        return (
            "Validate that measurements cover all hypothesis variables. "
            "Checks if IV, DV, and mediators are properly measured. "
            "Returns coverage score and missing variables."
        )

    @property
    def cost(self) -> float:
        return 0.1

    @property
    def category(self) -> str:
        return "validation"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="hypothesis",
                type="dict",
                description="Structured hypothesis with variables",
                required=True,
            ),
            ToolParameter(
                name="measurements",
                type="list",
                description="List of measurements",
                required=True,
            ),
        ]

    async def run(
        self,
        hypothesis: dict,
        measurements: list[dict],
    ) -> dict[str, Any]:
        """Validate measurement coverage.

        Args:
            hypothesis: Structured hypothesis
            measurements: List of measurements

        Returns:
            Coverage validation results
        """
        logger.info("Validating measurement coverage...")

        # Extract required variables
        required_vars = set()
        if iv := hypothesis.get("iv"):
            required_vars.add(iv.lower())
        if dv := hypothesis.get("dv"):
            required_vars.add(dv.lower())
        if mediators := hypothesis.get("mediators"):
            required_vars.update(m.lower() for m in mediators)
        if moderators := hypothesis.get("moderators"):
            required_vars.update(m.lower() for m in moderators)

        # Extract measured variables
        measured_vars = set()
        for m in measurements:
            if target := m.get("target"):
                measured_vars.add(target.lower())
            if targets := m.get("targets"):
                measured_vars.update(t.lower() for t in targets)
            if readout := m.get("readout"):
                measured_vars.add(readout.lower())

        # Calculate coverage
        covered = required_vars & measured_vars
        missing = required_vars - measured_vars

        coverage = len(covered) / len(required_vars) if required_vars else 1.0

        return {
            "coverage": coverage,
            "required_vars": list(required_vars),
            "covered_vars": list(covered),
            "missing_vars": list(missing),
            "total_measurements": len(measurements),
            "is_sufficient": coverage >= 0.8,
            "suggestions": [
                f"Add measurement for: {var}" for var in missing
            ] if missing else [],
        }
