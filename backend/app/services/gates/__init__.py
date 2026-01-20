"""Gates - Quality validation gates for RAG pipeline.

Gate 2: Retrieval Confidence (OAR-12)
- Validates search result quality before answer generation
"""

from .gate2_retrieval import gate2_service, Gate2Result

__all__ = ["gate2_service", "Gate2Result"]
