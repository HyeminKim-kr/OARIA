"""Study Plan Agent v3 - Multi-Tier Search Module

3-tier 검색 스택:
- Tier 1: RAG (Weaviate) - 내부 벡터 DB
- Tier 2: Europe PMC - 오픈 액세스 논문 DB
- Tier 3: Tavily Web - 웹 검색 (예산 제한)
"""

from .types import (
    SearchTier,
    SearchObjective,
    EvidenceSnippetV3,
    QueryPlan,
    DP1RouterInput,
    DP1RouterOutput,
)
from .budget_manager import SearchBudgetManager
from .cache_manager import SearchCacheManager
from .europe_pmc_service import EuropePmcService
from .tavily_service import TavilyService
from .multi_tier_search import MultiTierSearchService

__all__ = [
    # Types
    "SearchTier",
    "SearchObjective",
    "EvidenceSnippetV3",
    "QueryPlan",
    "DP1RouterInput",
    "DP1RouterOutput",
    # Services
    "SearchBudgetManager",
    "SearchCacheManager",
    "EuropePmcService",
    "TavilyService",
    "MultiTierSearchService",
]
