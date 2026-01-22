"""Tests for v4 long-term memory system."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.agent.study_plan.v4.memory.long_term import LongTermMemory


# ─────────────────────────────────────────────────────────────
# LongTermMemory Initialization Tests
# ─────────────────────────────────────────────────────────────


class TestLongTermMemoryInit:
    """Test LongTermMemory initialization."""

    def test_init_without_dependencies(self):
        """Test initialization without Redis or vector store."""
        memory = LongTermMemory()

        assert memory._redis is None
        assert memory._vector_store is None
        assert memory._local_cache == {}

    def test_init_with_redis(self):
        """Test initialization with Redis client."""
        mock_redis = MagicMock()
        memory = LongTermMemory(redis_client=mock_redis)

        assert memory._redis == mock_redis

    def test_init_with_vector_store(self):
        """Test initialization with vector store."""
        mock_vector_store = MagicMock()
        memory = LongTermMemory(vector_store=mock_vector_store)

        assert memory._vector_store == mock_vector_store


# ─────────────────────────────────────────────────────────────
# store_run Tests
# ─────────────────────────────────────────────────────────────


class TestStoreRun:
    """Test store_run method."""

    @pytest.mark.asyncio
    async def test_store_run_local_cache(self):
        """Test storing run in local cache."""
        memory = LongTermMemory()

        result = await memory.store_run(
            run_id="test-run-123",
            hypothesis="EGFR mutation causes resistance",
            result={
                "success": True,
                "quality_score": 0.85,
                "experiment_count": 3,
                "iteration_count": 15,
            },
        )

        assert result is True
        assert "test-run-123" in memory._local_cache
        assert memory._local_cache["test-run-123"]["hypothesis"] == "EGFR mutation causes resistance"

    @pytest.mark.asyncio
    async def test_store_run_with_metadata(self):
        """Test storing run with metadata."""
        memory = LongTermMemory()
        metadata = {"user_id": "user-456", "model": "gpt-4"}

        await memory.store_run(
            run_id="test-run-123",
            hypothesis="Test hypothesis",
            result={"success": True},
            metadata=metadata,
        )

        stored = memory._local_cache["test-run-123"]
        assert stored["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_store_run_result_summary(self):
        """Test that result summary is correctly extracted."""
        memory = LongTermMemory()

        await memory.store_run(
            run_id="test-run-123",
            hypothesis="Test hypothesis",
            result={
                "success": True,
                "quality_score": 0.9,
                "experiment_count": 5,
                "iteration_count": 20,
                "extra_field": "ignored",
            },
        )

        summary = memory._local_cache["test-run-123"]["result_summary"]
        assert summary["success"] is True
        assert summary["quality_score"] == 0.9
        assert summary["experiment_count"] == 5
        assert summary["iteration_count"] == 20

    @pytest.mark.asyncio
    async def test_store_run_with_redis(self):
        """Test storing run with Redis."""
        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock()
        mock_redis.sadd = AsyncMock()

        memory = LongTermMemory(redis_client=mock_redis)

        result = await memory.store_run(
            run_id="test-run-123",
            hypothesis="Test hypothesis",
            result={"success": True},
        )

        assert result is True
        mock_redis.setex.assert_called_once()
        # Check that key contains run_id
        call_args = mock_redis.setex.call_args
        assert "test-run-123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_store_run_handles_error(self):
        """Test that store_run handles errors gracefully."""
        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Connection error"))

        memory = LongTermMemory(redis_client=mock_redis)

        result = await memory.store_run(
            run_id="test-run-123",
            hypothesis="Test hypothesis",
            result={"success": True},
        )

        assert result is False


# ─────────────────────────────────────────────────────────────
# recall_similar Tests
# ─────────────────────────────────────────────────────────────


class TestRecallSimilar:
    """Test recall_similar method."""

    @pytest.mark.asyncio
    async def test_recall_similar_empty_cache(self):
        """Test recall with empty cache returns empty list."""
        memory = LongTermMemory()

        results = await memory.recall_similar("Test hypothesis")

        assert results == []

    @pytest.mark.asyncio
    async def test_recall_similar_local_search(self):
        """Test recall using local cache search."""
        memory = LongTermMemory()

        # Store some runs
        await memory.store_run(
            run_id="run-1",
            hypothesis="EGFR mutation causes drug resistance",
            result={"success": True, "quality_score": 0.8},
        )
        await memory.store_run(
            run_id="run-2",
            hypothesis="KRAS mutation affects treatment response",
            result={"success": True, "quality_score": 0.9},
        )
        await memory.store_run(
            run_id="run-3",
            hypothesis="EGFR inhibitor improves outcomes",
            result={"success": False, "quality_score": 0.5},
        )

        # Search for similar to EGFR-related hypothesis
        results = await memory.recall_similar("EGFR mutation leads to resistance", top_k=2)

        # Should find runs with matching keywords
        assert len(results) <= 2
        hypotheses = [r["hypothesis"] for r in results]
        # Should prioritize runs with EGFR keyword
        assert any("EGFR" in h for h in hypotheses)

    @pytest.mark.asyncio
    async def test_recall_similar_respects_top_k(self):
        """Test that recall_similar respects top_k limit."""
        memory = LongTermMemory()

        # Store multiple runs
        for i in range(10):
            await memory.store_run(
                run_id=f"run-{i}",
                hypothesis=f"Hypothesis about cancer mutation type {i}",
                result={"success": True},
            )

        results = await memory.recall_similar("cancer mutation", top_k=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_recall_similar_handles_error(self):
        """Test that recall handles errors gracefully."""
        memory = LongTermMemory()
        # Corrupt local cache to cause error
        memory._local_cache = None  # type: ignore

        results = await memory.recall_similar("Test hypothesis")

        assert results == []


# ─────────────────────────────────────────────────────────────
# get_common_failures Tests
# ─────────────────────────────────────────────────────────────


class TestGetCommonFailures:
    """Test get_common_failures method."""

    @pytest.mark.asyncio
    async def test_get_common_failures_empty(self):
        """Test get_common_failures with no data."""
        memory = LongTermMemory()

        failures = await memory.get_common_failures()

        assert failures == []

    @pytest.mark.asyncio
    async def test_get_common_failures_returns_failed_runs(self):
        """Test that get_common_failures returns failed runs."""
        memory = LongTermMemory()

        # Store successful and failed runs
        await memory.store_run(
            run_id="success-1",
            hypothesis="Successful hypothesis",
            result={"success": True, "quality_score": 0.9},
        )
        await memory.store_run(
            run_id="fail-1",
            hypothesis="Failed hypothesis 1",
            result={"success": False, "quality_score": 0.4},
        )
        await memory.store_run(
            run_id="fail-2",
            hypothesis="Failed hypothesis 2",
            result={"success": False, "quality_score": 0.3},
        )

        failures = await memory.get_common_failures()

        assert len(failures) == 2
        # All should be failures
        assert all(f["quality_score"] < 0.5 for f in failures)

    @pytest.mark.asyncio
    async def test_get_common_failures_handles_error(self):
        """Test that get_common_failures handles errors gracefully."""
        memory = LongTermMemory()
        memory._local_cache = None  # type: ignore

        failures = await memory.get_common_failures()

        assert failures == []


# ─────────────────────────────────────────────────────────────
# get_best_practices Tests
# ─────────────────────────────────────────────────────────────


class TestGetBestPractices:
    """Test get_best_practices method."""

    @pytest.mark.asyncio
    async def test_get_best_practices_empty(self):
        """Test get_best_practices with no data."""
        memory = LongTermMemory()

        practices = await memory.get_best_practices()

        assert practices == []

    @pytest.mark.asyncio
    async def test_get_best_practices_returns_high_quality_runs(self):
        """Test that get_best_practices returns high quality runs."""
        memory = LongTermMemory()

        # Store runs with varying quality
        await memory.store_run(
            run_id="low-quality",
            hypothesis="Low quality hypothesis",
            result={"success": True, "quality_score": 0.6, "experiment_count": 2},
        )
        await memory.store_run(
            run_id="high-quality",
            hypothesis="High quality hypothesis",
            result={"success": True, "quality_score": 0.9, "experiment_count": 5},
        )
        await memory.store_run(
            run_id="failed",
            hypothesis="Failed hypothesis",
            result={"success": False, "quality_score": 0.85, "experiment_count": 4},
        )

        practices = await memory.get_best_practices()

        # Should only include successful runs with quality >= 0.8
        assert len(practices) == 1
        assert practices[0]["quality_score"] == 0.9

    @pytest.mark.asyncio
    async def test_get_best_practices_sorted_by_quality(self):
        """Test that best practices are sorted by quality score."""
        memory = LongTermMemory()

        await memory.store_run(
            run_id="medium",
            hypothesis="Medium quality",
            result={"success": True, "quality_score": 0.85, "experiment_count": 3},
        )
        await memory.store_run(
            run_id="highest",
            hypothesis="Highest quality",
            result={"success": True, "quality_score": 0.95, "experiment_count": 5},
        )
        await memory.store_run(
            run_id="high",
            hypothesis="High quality",
            result={"success": True, "quality_score": 0.88, "experiment_count": 4},
        )

        practices = await memory.get_best_practices()

        assert len(practices) == 3
        assert practices[0]["quality_score"] == 0.95
        assert practices[1]["quality_score"] == 0.88
        assert practices[2]["quality_score"] == 0.85

    @pytest.mark.asyncio
    async def test_get_best_practices_limits_to_5(self):
        """Test that best practices returns at most 5 results."""
        memory = LongTermMemory()

        # Store 10 high quality runs
        for i in range(10):
            await memory.store_run(
                run_id=f"run-{i}",
                hypothesis=f"Hypothesis {i}",
                result={"success": True, "quality_score": 0.9, "experiment_count": 3},
            )

        practices = await memory.get_best_practices()

        assert len(practices) <= 5


# ─────────────────────────────────────────────────────────────
# Keyword Extraction Tests
# ─────────────────────────────────────────────────────────────


class TestKeywordExtraction:
    """Test _extract_keywords method."""

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        memory = LongTermMemory()

        keywords = memory._extract_keywords("EGFR mutation causes drug resistance")

        assert "egfr" in keywords
        assert "mutation" in keywords
        assert "causes" in keywords
        assert "drug" in keywords
        assert "resistance" in keywords

    def test_extract_keywords_removes_stopwords(self):
        """Test that stopwords are removed."""
        memory = LongTermMemory()

        keywords = memory._extract_keywords("The effect of the drug on the patient")

        assert "the" not in keywords
        assert "effect" in keywords
        assert "drug" in keywords
        assert "patient" in keywords

    def test_extract_keywords_removes_short_words(self):
        """Test that short words are removed."""
        memory = LongTermMemory()

        keywords = memory._extract_keywords("A is B and C or D")

        # Short words (< 3 chars) should be excluded
        assert all(len(k) >= 3 for k in keywords)

    def test_extract_keywords_limits_count(self):
        """Test that keyword count is limited."""
        memory = LongTermMemory()

        long_text = " ".join([f"keyword{i}" for i in range(50)])
        keywords = memory._extract_keywords(long_text)

        assert len(keywords) <= 20

    def test_extract_keywords_unique(self):
        """Test that keywords are unique."""
        memory = LongTermMemory()

        keywords = memory._extract_keywords("mutation mutation mutation drug drug")

        # Should have unique keywords only
        assert len(keywords) == len(set(keywords))


# ─────────────────────────────────────────────────────────────
# Local Search Tests
# ─────────────────────────────────────────────────────────────


class TestLocalSearch:
    """Test _local_search method."""

    def test_local_search_empty_cache(self):
        """Test local search with empty cache."""
        memory = LongTermMemory()

        results = memory._local_search("Test hypothesis", top_k=3)

        assert results == []

    def test_local_search_finds_matches(self):
        """Test that local search finds matching records."""
        memory = LongTermMemory()

        # Add some records directly to cache
        memory._local_cache = {
            "run-1": {
                "run_id": "run-1",
                "hypothesis": "EGFR mutation causes resistance",
                "result_summary": {"success": True},
            },
            "run-2": {
                "run_id": "run-2",
                "hypothesis": "KRAS affects treatment",
                "result_summary": {"success": True},
            },
        }

        results = memory._local_search("EGFR related hypothesis", top_k=3)

        # Should find the EGFR-related record
        assert len(results) >= 1

    def test_local_search_ranks_by_overlap(self):
        """Test that local search ranks by keyword overlap."""
        memory = LongTermMemory()

        memory._local_cache = {
            "run-1": {
                "run_id": "run-1",
                "hypothesis": "EGFR mutation drug resistance cancer",
                "result_summary": {"success": True},
            },
            "run-2": {
                "run_id": "run-2",
                "hypothesis": "EGFR mutation",
                "result_summary": {"success": True},
            },
        }

        results = memory._local_search("EGFR mutation drug resistance", top_k=2)

        # First result should have more overlap
        assert len(results) == 2
        # run-1 has more keyword overlap
        assert results[0]["run_id"] == "run-1"

    def test_local_search_respects_top_k(self):
        """Test that local search respects top_k."""
        memory = LongTermMemory()

        # Add many matching records
        for i in range(10):
            memory._local_cache[f"run-{i}"] = {
                "run_id": f"run-{i}",
                "hypothesis": f"Cancer mutation treatment therapy {i}",
                "result_summary": {"success": True},
            }

        results = memory._local_search("cancer mutation treatment", top_k=3)

        assert len(results) <= 3


# ─────────────────────────────────────────────────────────────
# Redis Integration Tests (Mocked)
# ─────────────────────────────────────────────────────────────


class TestRedisIntegration:
    """Test Redis integration with mocks."""

    @pytest.mark.asyncio
    async def test_index_by_hypothesis(self):
        """Test hypothesis indexing in Redis."""
        mock_redis = MagicMock()
        mock_redis.sadd = AsyncMock()

        memory = LongTermMemory(redis_client=mock_redis)

        await memory._index_by_hypothesis("run-123", "EGFR mutation causes resistance")

        # Should add run_id to keyword indices
        assert mock_redis.sadd.call_count > 0

    @pytest.mark.asyncio
    async def test_keyword_search_redis(self):
        """Test keyword search using Redis."""
        mock_redis = MagicMock()
        mock_redis.smembers = AsyncMock(return_value={"run-1", "run-2"})
        mock_redis.get = AsyncMock(
            return_value='{"run_id": "run-1", "hypothesis": "test"}'
        )

        memory = LongTermMemory(redis_client=mock_redis)

        results = await memory._keyword_search("test hypothesis", top_k=3)

        mock_redis.smembers.assert_called()
        assert len(results) <= 3
