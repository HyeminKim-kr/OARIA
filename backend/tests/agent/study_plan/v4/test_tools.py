"""Tests for v4 tool system - ToolRegistry, BaseTool, and individual tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent.study_plan.v4.tools.base import (
    BaseTool,
    ToolParameter,
    ToolDefinition,
)
from app.services.agent.study_plan.v4.tools.registry import (
    ToolRegistry,
    create_default_registry,
)


# ─────────────────────────────────────────────────────────────
# ToolParameter Tests
# ─────────────────────────────────────────────────────────────


class TestToolParameter:
    """Test ToolParameter dataclass."""

    def test_create_required_parameter(self):
        """Test creating a required parameter."""
        param = ToolParameter(
            name="query",
            type="str",
            description="Search query",
            required=True,
        )

        assert param.name == "query"
        assert param.type == "str"
        assert param.description == "Search query"
        assert param.required is True
        assert param.default is None

    def test_create_optional_parameter_with_default(self):
        """Test creating an optional parameter with default."""
        param = ToolParameter(
            name="limit",
            type="int",
            description="Maximum results",
            required=False,
            default=10,
        )

        assert param.name == "limit"
        assert param.required is False
        assert param.default == 10


# ─────────────────────────────────────────────────────────────
# ToolDefinition Tests
# ─────────────────────────────────────────────────────────────


class TestToolDefinition:
    """Test ToolDefinition dataclass."""

    def test_create_tool_definition(self):
        """Test creating a tool definition."""
        params = [
            ToolParameter(name="query", type="str", description="Search query"),
        ]
        definition = ToolDefinition(
            name="search_tool",
            description="Search for papers",
            parameters=params,
            cost="medium",
            category="search",
        )

        assert definition.name == "search_tool"
        assert definition.description == "Search for papers"
        assert len(definition.parameters) == 1
        assert definition.cost == "medium"
        assert definition.category == "search"

    def test_to_llm_description_with_parameters(self):
        """Test LLM description generation with parameters."""
        params = [
            ToolParameter(name="query", type="str", description="Search query"),
            ToolParameter(
                name="limit", type="int", description="Max results", required=False
            ),
        ]
        definition = ToolDefinition(
            name="search_tool",
            description="Search for papers",
            parameters=params,
            cost="low",
        )

        llm_desc = definition.to_llm_description()

        assert "**search_tool**" in llm_desc
        assert "[low cost]" in llm_desc
        assert "Search for papers" in llm_desc
        assert "query (str, required)" in llm_desc
        assert "limit (int, optional)" in llm_desc

    def test_to_llm_description_without_parameters(self):
        """Test LLM description generation without parameters."""
        definition = ToolDefinition(
            name="finish",
            description="Finish execution",
            parameters=[],
        )

        llm_desc = definition.to_llm_description()

        assert "(no parameters)" in llm_desc


# ─────────────────────────────────────────────────────────────
# BaseTool Tests
# ─────────────────────────────────────────────────────────────


class TestBaseTool:
    """Test BaseTool abstract class."""

    def test_mock_tool_properties(self, mock_tool):
        """Test MockTool has correct properties."""
        assert mock_tool.name == "mock_tool"
        assert "Mock tool" in mock_tool.description
        assert mock_tool.category == "test"
        assert mock_tool.cost == 0.1  # Default

    def test_mock_tool_get_definition(self, mock_tool):
        """Test get_definition returns correct ToolDefinition."""
        definition = mock_tool.get_definition()

        assert isinstance(definition, ToolDefinition)
        assert definition.name == "mock_tool"
        assert definition.category == "test"

    @pytest.mark.asyncio
    async def test_mock_tool_run(self, mock_tool):
        """Test MockTool.run() returns expected result."""
        result = await mock_tool.run(input="test")

        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_mock_tool_validate_input_missing_required(self):
        """Test validate_input catches missing required params."""

        class ToolWithRequired(BaseTool):
            @property
            def name(self):
                return "required_tool"

            @property
            def description(self):
                return "Tool with required param"

            def _get_parameters(self):
                return [
                    ToolParameter(
                        name="required_param",
                        type="str",
                        description="Required",
                        required=True,
                    )
                ]

            async def run(self, **kwargs):
                return {}

        tool = ToolWithRequired()
        is_valid, error = await tool.validate_input()

        assert is_valid is False
        assert "required_param" in error

    @pytest.mark.asyncio
    async def test_mock_tool_validate_input_success(self):
        """Test validate_input passes with all required params."""

        class ToolWithRequired(BaseTool):
            @property
            def name(self):
                return "required_tool"

            @property
            def description(self):
                return "Tool with required param"

            def _get_parameters(self):
                return [
                    ToolParameter(
                        name="query",
                        type="str",
                        description="Required",
                        required=True,
                    )
                ]

            async def run(self, **kwargs):
                return {}

        tool = ToolWithRequired()
        is_valid, error = await tool.validate_input(query="test")

        assert is_valid is True
        assert error is None

    def test_cost_to_string_low(self):
        """Test cost conversion to 'low'."""

        class LowCostTool(BaseTool):
            @property
            def name(self):
                return "low_cost"

            @property
            def description(self):
                return "Low cost tool"

            @property
            def cost(self):
                return 0.1

            async def run(self, **kwargs):
                return {}

        tool = LowCostTool()
        definition = tool.get_definition()
        assert definition.cost == "low"

    def test_cost_to_string_medium(self):
        """Test cost conversion to 'medium'."""

        class MediumCostTool(BaseTool):
            @property
            def name(self):
                return "medium_cost"

            @property
            def description(self):
                return "Medium cost tool"

            @property
            def cost(self):
                return 0.5

            async def run(self, **kwargs):
                return {}

        tool = MediumCostTool()
        definition = tool.get_definition()
        assert definition.cost == "medium"

    def test_cost_to_string_high(self):
        """Test cost conversion to 'high'."""

        class HighCostTool(BaseTool):
            @property
            def name(self):
                return "high_cost"

            @property
            def description(self):
                return "High cost tool"

            @property
            def cost(self):
                return 0.9

            async def run(self, **kwargs):
                return {}

        tool = HighCostTool()
        definition = tool.get_definition()
        assert definition.cost == "high"


# ─────────────────────────────────────────────────────────────
# ToolRegistry Tests
# ─────────────────────────────────────────────────────────────


class TestToolRegistry:
    """Test ToolRegistry class."""

    def test_registry_initialization(self):
        """Test empty registry initialization."""
        registry = ToolRegistry()

        assert len(registry) == 0
        assert registry.list_tools() == []
        assert registry.get_categories() == []

    def test_register_tool(self, mock_tool):
        """Test registering a tool."""
        registry = ToolRegistry()
        registry.register(mock_tool)

        assert len(registry) == 1
        assert "mock_tool" in registry
        assert mock_tool.name in registry.list_tools()

    def test_register_duplicate_raises_error(self, mock_tool):
        """Test that registering duplicate tool raises ValueError."""
        registry = ToolRegistry()
        registry.register(mock_tool)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(mock_tool)

    def test_get_tool(self, mock_tool):
        """Test getting a registered tool."""
        registry = ToolRegistry()
        registry.register(mock_tool)

        retrieved = registry.get("mock_tool")

        assert retrieved == mock_tool

    def test_get_nonexistent_tool(self):
        """Test getting a non-existent tool returns None."""
        registry = ToolRegistry()

        retrieved = registry.get("nonexistent")

        assert retrieved is None

    def test_list_by_category(self, mock_tool_registry):
        """Test listing tools by category."""
        # mock_tool_registry from conftest has tools in "test" category
        test_tools = mock_tool_registry.list_by_category("test")

        assert len(test_tools) > 0
        assert "parse_hypothesis" in test_tools

    def test_list_by_nonexistent_category(self):
        """Test listing tools by non-existent category."""
        registry = ToolRegistry()

        tools = registry.list_by_category("nonexistent")

        assert tools == []

    def test_get_categories(self, mock_tool_registry):
        """Test getting all categories."""
        categories = mock_tool_registry.get_categories()

        assert "test" in categories

    def test_contains(self, mock_tool):
        """Test __contains__ method."""
        registry = ToolRegistry()
        registry.register(mock_tool)

        assert "mock_tool" in registry
        assert "other_tool" not in registry

    def test_len(self, mock_tool_registry):
        """Test __len__ method."""
        assert len(mock_tool_registry) == 7  # From conftest fixtures

    def test_get_descriptions_for_llm(self, mock_tool_registry):
        """Test generating LLM descriptions."""
        descriptions = mock_tool_registry.get_descriptions_for_llm()

        assert isinstance(descriptions, str)
        assert "parse_hypothesis" in descriptions
        assert "decompose_questions" in descriptions

    def test_get_tool_summary(self, mock_tool_registry):
        """Test getting tool summary."""
        summary = mock_tool_registry.get_tool_summary()

        assert "total_tools" in summary
        assert "categories" in summary
        assert "tools" in summary
        assert summary["total_tools"] == 7


# ─────────────────────────────────────────────────────────────
# create_default_registry Tests
# ─────────────────────────────────────────────────────────────


class TestCreateDefaultRegistry:
    """Test create_default_registry function."""

    def test_creates_registry_with_all_tools(self):
        """Test that default registry contains all 15 tools."""
        registry = create_default_registry()

        assert len(registry) == 15

    def test_registry_has_search_tools(self):
        """Test registry has search category tools."""
        registry = create_default_registry()

        assert "search_rag" in registry
        assert "search_epmc" in registry
        assert "search_web" in registry

    def test_registry_has_analysis_tools(self):
        """Test registry has analysis category tools."""
        registry = create_default_registry()

        assert "parse_hypothesis" in registry
        assert "decompose_questions" in registry
        assert "analyze_methodology" in registry

    def test_registry_has_design_tools(self):
        """Test registry has design category tools."""
        registry = create_default_registry()

        assert "design_experiment" in registry
        assert "design_controls" in registry
        assert "suggest_measurements" in registry

    def test_registry_has_validation_tools(self):
        """Test registry has validation category tools."""
        registry = create_default_registry()

        assert "validate_controls" in registry
        assert "validate_coverage" in registry
        assert "critique_design" in registry

    def test_registry_has_synthesis_tools(self):
        """Test registry has synthesis category tools."""
        registry = create_default_registry()

        assert "synthesize_plan" in registry
        assert "generate_plan_b" in registry

    def test_registry_has_user_tool(self):
        """Test registry has user interaction tool."""
        registry = create_default_registry()

        assert "ask_user" in registry

    def test_each_tool_has_definition(self):
        """Test each registered tool has a valid definition."""
        registry = create_default_registry()

        for tool_name in registry.list_tools():
            tool = registry.get(tool_name)
            definition = tool.get_definition()

            assert definition.name == tool_name
            assert isinstance(definition.description, str)
            assert len(definition.description) > 0

    def test_registry_categories(self):
        """Test registry has expected categories."""
        registry = create_default_registry()

        categories = registry.get_categories()

        expected = ["search", "analysis", "design", "validation", "synthesis", "user"]
        for cat in expected:
            assert cat in categories


# ─────────────────────────────────────────────────────────────
# Individual Tool Tests
# ─────────────────────────────────────────────────────────────


class TestParseHypothesisTool:
    """Test ParseHypothesisTool."""

    def test_tool_properties(self):
        """Test tool has correct properties."""
        from app.services.agent.study_plan.v4.tools.analysis import ParseHypothesisTool

        tool = ParseHypothesisTool()

        assert tool.name == "parse_hypothesis"
        assert tool.category == "analysis"
        assert "hypothesis" in tool.description.lower()

    def test_tool_parameters(self):
        """Test tool has correct parameters."""
        from app.services.agent.study_plan.v4.tools.analysis import ParseHypothesisTool

        tool = ParseHypothesisTool()
        params = tool._get_parameters()

        param_names = [p.name for p in params]
        assert "hypothesis" in param_names


class TestDecomposeQuestionsTool:
    """Test DecomposeQuestionsTool."""

    def test_tool_properties(self):
        """Test tool has correct properties."""
        from app.services.agent.study_plan.v4.tools.analysis import (
            DecomposeQuestionsTool,
        )

        tool = DecomposeQuestionsTool()

        assert tool.name == "decompose_questions"
        assert tool.category == "analysis"

    def test_tool_parameters(self):
        """Test tool has correct parameters."""
        from app.services.agent.study_plan.v4.tools.analysis import (
            DecomposeQuestionsTool,
        )

        tool = DecomposeQuestionsTool()
        params = tool._get_parameters()

        param_names = [p.name for p in params]
        assert "structured_hypothesis" in param_names


class TestSearchTools:
    """Test search category tools."""

    def test_rag_search_tool(self):
        """Test RAGSearchTool properties."""
        from app.services.agent.study_plan.v4.tools.search import RAGSearchTool

        tool = RAGSearchTool()

        assert tool.name == "search_rag"
        assert tool.category == "search"
        assert tool.cost < 0.3  # Low cost

    def test_epmc_search_tool(self):
        """Test EPMCSearchTool properties."""
        from app.services.agent.study_plan.v4.tools.search import EPMCSearchTool

        tool = EPMCSearchTool()

        assert tool.name == "search_epmc"
        assert tool.category == "search"
        assert 0.3 <= tool.cost < 0.7  # Medium cost

    def test_web_search_tool(self):
        """Test WebSearchTool properties."""
        from app.services.agent.study_plan.v4.tools.search import WebSearchTool

        tool = WebSearchTool()

        assert tool.name == "search_web"
        assert tool.category == "search"
        assert tool.cost >= 0.7  # High cost


class TestDesignTools:
    """Test design category tools."""

    def test_design_experiment_tool(self):
        """Test DesignExperimentTool properties."""
        from app.services.agent.study_plan.v4.tools.design import DesignExperimentTool

        tool = DesignExperimentTool()

        assert tool.name == "design_experiment"
        assert tool.category == "design"

    def test_design_controls_tool(self):
        """Test DesignControlsTool properties."""
        from app.services.agent.study_plan.v4.tools.design import DesignControlsTool

        tool = DesignControlsTool()

        assert tool.name == "design_controls"
        assert tool.category == "design"

    def test_suggest_measurements_tool(self):
        """Test SuggestMeasurementsTool properties."""
        from app.services.agent.study_plan.v4.tools.design import SuggestMeasurementsTool

        tool = SuggestMeasurementsTool()

        assert tool.name == "suggest_measurements"
        assert tool.category == "design"


class TestValidationTools:
    """Test validation category tools."""

    def test_validate_controls_tool(self):
        """Test ValidateControlsTool properties."""
        from app.services.agent.study_plan.v4.tools.validation import ValidateControlsTool

        tool = ValidateControlsTool()

        assert tool.name == "validate_controls"
        assert tool.category == "validation"

    def test_validate_coverage_tool(self):
        """Test ValidateCoverageTool properties."""
        from app.services.agent.study_plan.v4.tools.validation import ValidateCoverageTool

        tool = ValidateCoverageTool()

        assert tool.name == "validate_coverage"
        assert tool.category == "validation"

    def test_critique_design_tool(self):
        """Test CritiqueDesignTool properties."""
        from app.services.agent.study_plan.v4.tools.validation import CritiqueDesignTool

        tool = CritiqueDesignTool()

        assert tool.name == "critique_design"
        assert tool.category == "validation"


class TestSynthesisTools:
    """Test synthesis category tools."""

    def test_synthesize_plan_tool(self):
        """Test SynthesizePlanTool properties."""
        from app.services.agent.study_plan.v4.tools.synthesis import SynthesizePlanTool

        tool = SynthesizePlanTool()

        assert tool.name == "synthesize_plan"
        assert tool.category == "synthesis"

    def test_generate_plan_b_tool(self):
        """Test GeneratePlanBTool properties."""
        from app.services.agent.study_plan.v4.tools.synthesis import GeneratePlanBTool

        tool = GeneratePlanBTool()

        assert tool.name == "generate_plan_b"
        assert tool.category == "synthesis"


class TestUserTool:
    """Test user interaction tool."""

    def test_ask_user_tool(self):
        """Test AskUserTool properties."""
        from app.services.agent.study_plan.v4.tools.user import AskUserTool

        tool = AskUserTool()

        assert tool.name == "ask_user"
        assert tool.category == "user"
        assert tool.cost >= 0.7  # High cost (interrupts user)
