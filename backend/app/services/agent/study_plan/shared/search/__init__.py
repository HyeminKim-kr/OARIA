"""Search 모듈

3-tier 검색 (RAG → EPMC → Web) 관련 타입 및 서비스.
"""

from .types import (
    SearchTier,
    SearchObjective,
    EvidenceSnippetV3,
    DP1RouterInput,
    DP1RouterOutput,
    DP2RouterInput,
    DP2RouterOutput,
    DP3RouterInput,
    DP3RouterOutput,
)
from .budget_manager import budget_manager, SearchBudgetManager, RunBudget
from .cache_manager import cache_manager, SearchCacheManager
from .europe_pmc_service import europe_pmc_service, EuropePmcService
from .tavily_service import tavily_service, TavilyService
from .multi_tier_search import multi_tier_search, MultiTierSearchService, SearchResult

__all__ = [
    # Types
    "SearchTier",
    "SearchObjective",
    "EvidenceSnippetV3",
    "DP1RouterInput",
    "DP1RouterOutput",
    "DP2RouterInput",
    "DP2RouterOutput",
    "DP3RouterInput",
    "DP3RouterOutput",
    # Budget
    "budget_manager",
    "SearchBudgetManager",
    "RunBudget",
    # Cache
    "cache_manager",
    "SearchCacheManager",
    # Services
    "europe_pmc_service",
    "EuropePmcService",
    "tavily_service",
    "TavilyService",
    "multi_tier_search",
    "MultiTierSearchService",
    "SearchResult",
]
