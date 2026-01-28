"""Long-term memory for v4 agent.

Stores past execution results and enables learning from previous runs.
Uses vector similarity to find relevant past experiences.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Long-term memory for storing and retrieving past runs.

    Supports:
    - Storing execution results
    - Retrieving similar past runs
    - Learning from failure patterns
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        vector_store: Any | None = None,
    ):
        """Initialize long-term memory.

        Args:
            redis_client: Optional Redis client for caching
            vector_store: Optional vector store for similarity search
        """
        self._redis = redis_client
        self._vector_store = vector_store
        self._local_cache: dict[str, dict] = {}  # Fallback if no Redis

    async def store_run(
        self,
        run_id: str,
        hypothesis: str,
        result: dict,
        metadata: dict | None = None,
    ) -> bool:
        """Store a completed run for future reference.

        Args:
            run_id: Unique run identifier
            hypothesis: The hypothesis that was tested
            result: Execution result
            metadata: Additional metadata

        Returns:
            True if stored successfully
        """
        record = {
            "run_id": run_id,
            "hypothesis": hypothesis,
            "result_summary": {
                "success": result.get("success", False),
                "quality_score": result.get("quality_score", 0),
                "experiment_count": result.get("experiment_count", 0),
                "iteration_count": result.get("iteration_count", 0),
            },
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            if self._redis:
                # Store in Redis with expiration (30 days)
                key = f"study_plan:run:{run_id}"
                await self._redis.setex(
                    key,
                    timedelta(days=30),
                    json.dumps(record),
                )

                # Add to hypothesis index for similarity search
                await self._index_by_hypothesis(run_id, hypothesis)

            else:
                # Fallback to local cache
                self._local_cache[run_id] = record

            logger.info(f"Stored run {run_id} in long-term memory")
            return True

        except Exception as e:
            logger.error(f"Failed to store run: {e}")
            return False

    async def recall_similar(
        self,
        hypothesis: str,
        top_k: int = 3,
    ) -> list[dict]:
        """Find similar past runs based on hypothesis.

        Args:
            hypothesis: Current hypothesis
            top_k: Number of similar runs to return

        Returns:
            List of similar past run summaries
        """
        try:
            if self._vector_store:
                # Use vector similarity search
                results = await self._vector_search(hypothesis, top_k)
                return results

            elif self._redis:
                # Fallback to keyword-based search
                results = await self._keyword_search(hypothesis, top_k)
                return results

            else:
                # Use local cache
                return self._local_search(hypothesis, top_k)

        except Exception as e:
            logger.error(f"Failed to recall similar runs: {e}")
            return []

    async def get_common_failures(
        self,
        hypothesis_type: str | None = None,
    ) -> list[dict]:
        """Get common failure patterns.

        Args:
            hypothesis_type: Optional filter by hypothesis type

        Returns:
            List of common failure patterns with counts
        """
        try:
            if self._redis:
                # Get failure patterns from Redis
                pattern_key = "study_plan:failures:*"
                # Implementation would scan Redis for failure patterns
                return []

            # Analyze local cache
            failures = []
            for record in self._local_cache.values():
                if not record["result_summary"]["success"]:
                    failures.append({
                        "hypothesis": record["hypothesis"][:100],
                        "quality_score": record["result_summary"]["quality_score"],
                    })

            return failures

        except Exception as e:
            logger.error(f"Failed to get failure patterns: {e}")
            return []

    async def get_best_practices(
        self,
        hypothesis_type: str | None = None,
    ) -> list[dict]:
        """Get best practices from successful runs.

        Args:
            hypothesis_type: Optional filter by hypothesis type

        Returns:
            List of successful patterns
        """
        try:
            successes = []
            for record in self._local_cache.values():
                result = record["result_summary"]
                if result["success"] and result["quality_score"] >= 0.8:
                    successes.append({
                        "hypothesis": record["hypothesis"][:100],
                        "quality_score": result["quality_score"],
                        "experiment_count": result["experiment_count"],
                    })

            # Sort by quality score
            successes.sort(key=lambda x: x["quality_score"], reverse=True)
            return successes[:5]

        except Exception as e:
            logger.error(f"Failed to get best practices: {e}")
            return []

    async def _index_by_hypothesis(self, run_id: str, hypothesis: str) -> None:
        """Index run by hypothesis for search."""
        if not self._redis:
            return

        # Extract keywords for indexing
        keywords = self._extract_keywords(hypothesis)
        for keyword in keywords:
            key = f"study_plan:index:{keyword.lower()}"
            await self._redis.sadd(key, run_id)

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text for indexing."""
        # Simple keyword extraction
        import re

        # Remove common words
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "in", "on",
            "at", "to", "for", "of", "and", "or", "but", "that", "this",
        }

        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        keywords = [w for w in words if w not in stopwords]

        return list(set(keywords))[:20]

    async def _vector_search(
        self,
        hypothesis: str,
        top_k: int,
    ) -> list[dict]:
        """Search using vector similarity."""
        if not self._vector_store:
            return []

        # Get embedding for hypothesis
        # embedding = await self._get_embedding(hypothesis)

        # Search vector store
        # results = await self._vector_store.search(embedding, top_k)

        # Placeholder
        return []

    async def _keyword_search(
        self,
        hypothesis: str,
        top_k: int,
    ) -> list[dict]:
        """Search using keyword matching in Redis."""
        if not self._redis:
            return []

        keywords = self._extract_keywords(hypothesis)
        run_ids = set()

        for keyword in keywords[:5]:
            key = f"study_plan:index:{keyword}"
            ids = await self._redis.smembers(key)
            run_ids.update(ids)

        # Fetch run records
        results = []
        for run_id in list(run_ids)[:top_k]:
            key = f"study_plan:run:{run_id}"
            data = await self._redis.get(key)
            if data:
                results.append(json.loads(data))

        return results

    def _local_search(
        self,
        hypothesis: str,
        top_k: int,
    ) -> list[dict]:
        """Search in local cache using simple matching."""
        hypothesis_lower = hypothesis.lower()
        keywords = self._extract_keywords(hypothesis)

        scored_results = []
        for record in self._local_cache.values():
            record_hypothesis = record["hypothesis"].lower()

            # Simple keyword overlap score
            record_keywords = set(self._extract_keywords(record_hypothesis))
            overlap = len(set(keywords) & record_keywords)

            if overlap > 0:
                scored_results.append((overlap, record))

        # Sort by overlap and return top_k
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in scored_results[:top_k]]
