"""Podcast agent tasks.

F-11: Fixed 3-task structure
- Task 1: RAG Search (only RAG call)
- Task 2: Paper Analysis (LLM)
- Task 3: Script Generation (LLM)
"""

from .rag_search import execute_rag_search
from .paper_analysis import execute_paper_analysis
from .script_generator import execute_script_generation

__all__ = [
    "execute_rag_search",
    "execute_paper_analysis",
    "execute_script_generation",
]
