"""Tool registry for v4 agent.

The registry manages all available tools and provides:
- Tool registration
- Tool lookup by name
- Tool descriptions for LLM
- Tool categorization
"""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools.

    Manages tool registration and lookup.
    Provides descriptions for LLM tool selection.
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool with same name already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already registered")

        self._tools[tool.name] = tool

        # Track by category
        category = tool.category
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)

        logger.debug(f"Registered tool: {tool.name} ({category})")

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> list[str]:
        """List tools in a specific category."""
        return self._categories.get(category, [])

    def get_categories(self) -> list[str]:
        """Get all tool categories."""
        return list(self._categories.keys())

    def get_descriptions_for_llm(self) -> str:
        """Generate tool descriptions for LLM context.

        Returns:
            Formatted string with all tool descriptions
        """
        sections = []

        # Group by category
        for category in sorted(self._categories.keys()):
            tool_names = self._categories[category]
            category_title = category.replace("_", " ").title()

            tool_descriptions = []
            for name in tool_names:
                tool = self._tools[name]
                definition = tool.get_definition()
                tool_descriptions.append(definition.to_llm_description())

            sections.append(
                f"## {category_title} Tools\n\n" + "\n\n".join(tool_descriptions)
            )

        return "\n\n---\n\n".join(sections)

    def get_tool_summary(self) -> dict[str, Any]:
        """Get summary of all tools.

        Returns:
            Dict with tool counts and categories
        """
        return {
            "total_tools": len(self._tools),
            "categories": {
                cat: len(tools) for cat, tools in self._categories.items()
            },
            "tools": [
                {
                    "name": tool.name,
                    "category": tool.category,
                    "cost": tool.cost,
                }
                for tool in self._tools.values()
            ],
        }

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def create_default_registry() -> ToolRegistry:
    """Create a registry with all default tools registered.

    Returns:
        Configured ToolRegistry
    """
    from app.services.agent.study_plan.v4.tools.search import (
        RAGSearchTool,
        EPMCSearchTool,
        WebSearchTool,
    )
    from app.services.agent.study_plan.v4.tools.analysis import (
        ParseHypothesisTool,
        DecomposeQuestionsTool,
        AnalyzeMethodologyTool,
    )
    from app.services.agent.study_plan.v4.tools.design import (
        DesignExperimentTool,
        DesignControlsTool,
        SuggestMeasurementsTool,
    )
    from app.services.agent.study_plan.v4.tools.validation import (
        ValidateControlsTool,
        ValidateCoverageTool,
        CritiqueDesignTool,
    )
    from app.services.agent.study_plan.v4.tools.synthesis import (
        SynthesizePlanTool,
        GeneratePlanBTool,
    )
    from app.services.agent.study_plan.v4.tools.user import AskUserTool

    registry = ToolRegistry()

    # Search tools
    registry.register(RAGSearchTool())
    registry.register(EPMCSearchTool())
    registry.register(WebSearchTool())

    # Analysis tools
    registry.register(ParseHypothesisTool())
    registry.register(DecomposeQuestionsTool())
    registry.register(AnalyzeMethodologyTool())

    # Design tools
    registry.register(DesignExperimentTool())
    registry.register(DesignControlsTool())
    registry.register(SuggestMeasurementsTool())

    # Validation tools
    registry.register(ValidateControlsTool())
    registry.register(ValidateCoverageTool())
    registry.register(CritiqueDesignTool())

    # Synthesis tools
    registry.register(SynthesizePlanTool())
    registry.register(GeneratePlanBTool())

    # User interaction
    registry.register(AskUserTool())

    logger.info(f"Created registry with {len(registry)} tools")
    return registry
