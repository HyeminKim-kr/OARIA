"""Base tool class for v4 agent tools."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def safe_get(data: dict | str | Any, key: str, default: Any = None) -> Any:
    """Safely get value from dict, handling string inputs.

    Args:
        data: dict or string (possibly JSON)
        key: Key to retrieve
        default: Default value if not found

    Returns:
        Value or default
    """
    if isinstance(data, dict):
        return data.get(key, default)
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed.get(key, default)
        except json.JSONDecodeError:
            pass
    return default


def ensure_dict(data: dict | str | Any, default: dict | None = None) -> dict:
    """Ensure data is a dict, parsing from JSON string if needed.

    Args:
        data: dict, JSON string, or other
        default: Default dict if parsing fails

    Returns:
        dict
    """
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
            # If it's a list or other type, wrap it
            return {"value": parsed, "_raw": data}
        except json.JSONDecodeError:
            # Plain string, wrap it
            return {"value": data, "_raw": data}
    return default or {"value": str(data) if data else "", "_raw": data}


def ensure_list(data: list | str | Any, default: list | None = None) -> list:
    """Ensure data is a list, parsing from JSON string if needed.

    Args:
        data: list, JSON string, or other
        default: Default list if parsing fails

    Returns:
        list
    """
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            return [parsed]  # Wrap single value
        except json.JSONDecodeError:
            # Plain string, wrap it
            return [data] if data else []
    if data is None:
        return default or []
    return [data]  # Wrap non-list value


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

    def _python_type_to_json_schema(self, python_type: str) -> dict:
        """Convert Python type string to JSON Schema type.

        Args:
            python_type: Python type string (str, int, float, list, dict, bool)

        Returns:
            JSON Schema type definition
        """
        type_mapping = {
            "str": {"type": "string"},
            "string": {"type": "string"},
            "int": {"type": "integer"},
            "integer": {"type": "integer"},
            "float": {"type": "number"},
            "number": {"type": "number"},
            "bool": {"type": "boolean"},
            "boolean": {"type": "boolean"},
            "list": {"type": "array", "items": {"type": "string"}},
            "array": {"type": "array", "items": {"type": "string"}},
            "dict": {"type": "object"},
            "object": {"type": "object"},
        }
        return type_mapping.get(python_type.lower(), {"type": "string"})

    def to_openai_function(self) -> dict:
        """Convert tool definition to OpenAI Function Calling format.

        This enables structured tool invocation with automatic
        parameter validation by OpenAI.

        Returns:
            OpenAI function definition dict
        """
        properties = {}
        required = []

        for p in self.parameters:
            prop_schema = self._python_type_to_json_schema(p.type)
            prop_schema["description"] = p.description

            # Add default if specified
            if p.default is not None:
                prop_schema["default"] = p.default

            properties[p.name] = prop_schema

            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


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
