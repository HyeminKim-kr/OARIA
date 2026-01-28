"""Validate coverage tool."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import (
    BaseTool,
    ToolParameter,
    ensure_dict,
    ensure_list,
    safe_get,
)

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
        hypothesis: dict | str | None = None,
        measurements: list | str | None = None,
    ) -> dict[str, Any]:
        """Validate measurement coverage.

        Args:
            hypothesis: Structured hypothesis
            measurements: List of measurements

        Returns:
            Coverage validation results
        """
        # Handle missing parameters
        if hypothesis is None or measurements is None:
            logger.warning("validate_coverage called with missing parameters")
            return {
                "coverage": 0.0,
                "covered_variables": [],
                "missing_variables": [],
                "error": "Missing required parameters. Need both hypothesis and measurements.",
                "suggestions": ["Parse hypothesis first, then suggest measurements"],
            }

        logger.info("Validating measurement coverage...")

        try:
            # 타입 안전 변환
            hyp = ensure_dict(hypothesis)
            meas_list = ensure_list(measurements, [])

            # Extract required variables
            required_vars = set()
            if iv := safe_get(hyp, "iv"):
                if isinstance(iv, str):
                    required_vars.add(iv.lower())
            if dv := safe_get(hyp, "dv"):
                if isinstance(dv, str):
                    required_vars.add(dv.lower())
            if mediators := safe_get(hyp, "mediators"):
                if isinstance(mediators, list):
                    for m in mediators:
                        if isinstance(m, str):
                            required_vars.add(m.lower())
            if moderators := safe_get(hyp, "moderators"):
                if isinstance(moderators, list):
                    for m in moderators:
                        if isinstance(m, str):
                            required_vars.add(m.lower())

            # Extract measured variables
            measured_vars = set()
            for m in meas_list:
                m_dict = ensure_dict(m) if not isinstance(m, dict) else m
                if target := safe_get(m_dict, "target"):
                    if isinstance(target, str):
                        measured_vars.add(target.lower())
                if targets := safe_get(m_dict, "targets"):
                    if isinstance(targets, list):
                        for t in targets:
                            if isinstance(t, str):
                                measured_vars.add(t.lower())
                if readout := safe_get(m_dict, "readout"):
                    if isinstance(readout, str):
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
                "total_measurements": len(meas_list),
                "is_sufficient": coverage >= 0.8,
                "suggestions": [
                    f"Add measurement for: {var}" for var in missing
                ] if missing else [],
            }
        except Exception as e:
            logger.error(f"Error validating coverage: {e}")
            return {
                "coverage": 0.0,
                "required_vars": [],
                "covered_vars": [],
                "missing_vars": [],
                "total_measurements": 0,
                "is_sufficient": False,
                "error": str(e),
            }
