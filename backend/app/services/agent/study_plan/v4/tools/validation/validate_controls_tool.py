"""Validate controls tool."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class ValidateControlsTool(BaseTool):
    """Validate experimental controls.

    Checks if controls are complete and appropriate.
    """

    @property
    def name(self) -> str:
        return "validate_controls"

    @property
    def description(self) -> str:
        return (
            "Validate that experimental controls are complete and appropriate. "
            "Checks for vehicle/negative controls, positive controls, and "
            "technical controls. Returns issues and suggestions."
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
                name="experiment",
                type="dict",
                description="Experiment design",
                required=True,
            ),
            ToolParameter(
                name="controls",
                type="list",
                description="List of controls to validate",
                required=True,
            ),
        ]

    async def run(
        self,
        experiment: dict,
        controls: list[dict],
    ) -> dict[str, Any]:
        """Validate controls.

        Args:
            experiment: Experiment design
            controls: List of controls

        Returns:
            Validation results with issues and suggestions
        """
        logger.info(f"Validating {len(controls)} controls...")

        issues = []
        suggestions = []

        # Check for required control types
        control_types = {c.get("type") for c in controls}

        has_vehicle = "vehicle" in control_types or "negative" in control_types
        has_positive = "positive" in control_types

        if not has_vehicle:
            issues.append({
                "type": "missing_vehicle",
                "severity": "high",
                "message": "Missing vehicle/negative control",
            })
            suggestions.append("Add a vehicle control to establish baseline")

        if not has_positive:
            issues.append({
                "type": "missing_positive",
                "severity": "high",
                "message": "Missing positive control",
            })
            suggestions.append("Add a positive control to validate assay function")

        # Check each control has required fields
        for i, control in enumerate(controls):
            if not control.get("purpose"):
                issues.append({
                    "type": "missing_purpose",
                    "severity": "medium",
                    "message": f"Control {i+1} missing purpose",
                })

            if not control.get("expected_outcome"):
                issues.append({
                    "type": "missing_outcome",
                    "severity": "low",
                    "message": f"Control {i+1} missing expected outcome",
                })

        valid = len([i for i in issues if i["severity"] == "high"]) == 0

        return {
            "valid": valid,
            "issues": issues,
            "suggestions": suggestions,
            "summary": {
                "has_vehicle": has_vehicle,
                "has_positive": has_positive,
                "total_controls": len(controls),
                "high_severity_issues": len([i for i in issues if i["severity"] == "high"]),
            },
        }
