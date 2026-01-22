"""Base tool class for v4 agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str  # "str", "int", "float", "list", "dict", "bool"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    """Complete definition of a tool for LLM consumption."""

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    cost: str = "low"  # "low", "medium", "high"
    category: str = "general"

    def to_llm_description(self) -> str:
        """Generate description for LLM tool selection."""
        param_lines = []
        for p in self.parameters:
            req = "required" if p.required else "optional"
            param_lines.append(f"    - {p.name} ({p.type}, {req}): {p.description}")

        params_str = "\n".join(param_lines) if param_lines else "    (no parameters)"

        return f"""**{self.name}** [{self.cost} cost]
  {self.description}
  Parameters:
{params_str}"""


class BaseTool(ABC):
    """Base class for all agent tools.

    Subclasses must implement:
    - get_definition(): Returns tool metadata
    - run(**kwargs): Executes the tool
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM."""
        pass

    @property
    def cost(self) -> float:
        """Relative cost of execution (0.0 to 1.0)."""
        return 0.1  # Default low cost

    @property
    def category(self) -> str:
        """Tool category for organization."""
        return "general"

    def get_definition(self) -> ToolDefinition:
        """Get the full tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self._get_parameters(),
            cost=self._cost_to_string(self.cost),
            category=self.category,
        )

    def _get_parameters(self) -> list[ToolParameter]:
        """Get parameter definitions. Override in subclasses."""
        return []

    def _cost_to_string(self, cost: float) -> str:
        """Convert numeric cost to string."""
        if cost < 0.3:
            return "low"
        elif cost < 0.7:
            return "medium"
        else:
            return "high"

    @abstractmethod
    async def run(self, **kwargs) -> Any:
        """Execute the tool.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool-specific result

        Raises:
            Exception on failure
        """
        pass

    async def validate_input(self, **kwargs) -> tuple[bool, str | None]:
        """Validate input parameters.

        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self._get_parameters():
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

        return True, None
