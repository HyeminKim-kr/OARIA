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
        experiment: dict | str | None = None,
        controls: list[dict] | str | None = None,
    ) -> dict[str, Any]:
        """Validate controls.

        Args:
            experiment: Experiment design (optional)
            controls: List of controls (can be dict list or JSON string)

        Returns:
            Validation results with issues and suggestions
        """
        import json

        # Handle missing parameters
        if controls is None:
            logger.warning("validate_controls called without controls parameter")
            return {
                "valid": False,
                "issues": [{"type": "no_input", "severity": "high", "message": "No controls provided to validate"}],
                "suggestions": ["Call design_controls first to create controls, then call validate_controls with the result"],
                "summary": {"has_vehicle": False, "has_positive": False, "total_controls": 0, "high_severity_issues": 1},
            }

        # controls가 문자열로 전달된 경우 파싱
        if isinstance(controls, str):
            try:
                controls = json.loads(controls)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse controls string: {controls[:100]}")
                return {
                    "valid": False,
                    "issues": [{"type": "parse_error", "severity": "high", "message": "Could not parse controls"}],
                    "suggestions": ["Provide controls as a list of dictionaries"],
                    "summary": {"has_vehicle": False, "has_positive": False, "total_controls": 0, "high_severity_issues": 1},
                }

        # controls가 list가 아닌 경우
        if not isinstance(controls, list):
            controls = [controls] if controls else []

        # controls 내부 항목이 dict가 아닌 경우 처리
        parsed_controls = []
        for c in controls:
            if isinstance(c, dict):
                parsed_controls.append(c)
            elif isinstance(c, str):
                try:
                    parsed_controls.append(json.loads(c))
                except json.JSONDecodeError:
                    # 문자열 설명인 경우 기본 dict로 변환
                    parsed_controls.append({"type": "unknown", "description": c})
        controls = parsed_controls

        logger.info(f"Validating {len(controls)} controls...")

        issues = []
        suggestions = []

        # Check for required control types
        control_types = {c.get("type", "unknown") for c in controls}

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
            # control이 dict가 아닐 수 있음
            if isinstance(control, dict):
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
