"""Checkpointer configuration for LangGraph agent.

Provides checkpoint persistence for:
- Interruption recovery
- Session replay
- State inspection
"""

import logging
from typing import Optional, Literal
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


# ============================================================================
# Checkpointer Types
# ============================================================================

CheckpointerType = Literal["memory", "postgres", "none"]


# ============================================================================
# Checkpointer Factory
# ============================================================================

def create_checkpointer(
    checkpointer_type: CheckpointerType = "memory",
    **kwargs,
) -> Optional[BaseCheckpointSaver]:
    """Create a checkpointer instance based on type.

    Args:
        checkpointer_type: Type of checkpointer to create
            - "memory": In-memory checkpointer (development)
            - "postgres": PostgreSQL checkpointer (production)
            - "none": No checkpointing

    Returns:
        Checkpointer instance or None
    """
    if checkpointer_type == "none":
        logger.info("Checkpointing disabled")
        return None

    if checkpointer_type == "memory":
        logger.info("Using in-memory checkpointer")
        return MemorySaver()

    if checkpointer_type == "postgres":
        return _create_postgres_checkpointer(**kwargs)

    raise ValueError(f"Unknown checkpointer type: {checkpointer_type}")


def _create_postgres_checkpointer(**kwargs) -> BaseCheckpointSaver:
    """Create PostgreSQL-based checkpointer.

    Requires langgraph-checkpoint-postgres package.

    Args:
        **kwargs: Connection parameters
            - connection_string: PostgreSQL connection string
            - pool_size: Connection pool size

    Returns:
        PostgreSQL checkpointer instance
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        connection_string = kwargs.get("connection_string")
        if not connection_string:
            raise ValueError("PostgreSQL connection string required")

        pool_size = kwargs.get("pool_size", 5)

        logger.info(f"Using PostgreSQL checkpointer (pool_size={pool_size})")

        return PostgresSaver.from_conn_string(
            connection_string,
            pool_size=pool_size,
        )

    except ImportError:
        logger.error(
            "PostgreSQL checkpointer requires langgraph-checkpoint-postgres. "
            "Install with: pip install langgraph-checkpoint-postgres"
        )
        raise


# ============================================================================
# Checkpointer Context Manager
# ============================================================================

@asynccontextmanager
async def checkpointer_context(
    checkpointer_type: CheckpointerType = "memory",
    **kwargs,
):
    """Context manager for checkpointer lifecycle.

    Handles proper setup and teardown of checkpointer resources.

    Args:
        checkpointer_type: Type of checkpointer to create
        **kwargs: Checkpointer-specific configuration

    Yields:
        Checkpointer instance
    """
    checkpointer = create_checkpointer(checkpointer_type, **kwargs)

    try:
        # Setup (if needed)
        if hasattr(checkpointer, "setup"):
            await checkpointer.setup()

        yield checkpointer

    finally:
        # Cleanup (if needed)
        if hasattr(checkpointer, "cleanup"):
            await checkpointer.cleanup()


# ============================================================================
# Thread/Session Management
# ============================================================================

def create_thread_config(
    thread_id: str,
    checkpoint_ns: str = "study_plan_v4",
    max_iterations: int = 30,
) -> dict:
    """Create configuration for a specific thread/session.

    Args:
        thread_id: Unique thread identifier (e.g., job_id, run_id)
        checkpoint_ns: Namespace for checkpoints
        max_iterations: Maximum agent iterations (affects recursion_limit)

    Returns:
        Configuration dictionary for graph execution
    """
    # Each iteration has multiple node executions (reason, execute, observe, etc.)
    # Set recursion_limit to accommodate all iterations + buffer
    recursion_limit = max_iterations * 5 + 10  # 5 nodes per iteration + buffer

    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        },
        "recursion_limit": recursion_limit,
    }


async def get_thread_state(
    checkpointer: BaseCheckpointSaver,
    thread_id: str,
    checkpoint_ns: str = "study_plan_v4",
) -> Optional[dict]:
    """Get the latest state for a thread.

    Args:
        checkpointer: Checkpointer instance
        thread_id: Thread identifier
        checkpoint_ns: Checkpoint namespace

    Returns:
        Latest state dictionary or None if not found
    """
    if checkpointer is None:
        return None

    config = create_thread_config(thread_id, checkpoint_ns)

    try:
        checkpoint = await checkpointer.aget(config)
        if checkpoint:
            return checkpoint.get("channel_values", {})
        return None

    except Exception as e:
        logger.warning(f"Failed to get thread state: {e}")
        return None


async def list_thread_history(
    checkpointer: BaseCheckpointSaver,
    thread_id: str,
    checkpoint_ns: str = "study_plan_v4",
    limit: int = 10,
) -> list[dict]:
    """List checkpoint history for a thread.

    Args:
        checkpointer: Checkpointer instance
        thread_id: Thread identifier
        checkpoint_ns: Checkpoint namespace
        limit: Maximum number of checkpoints to return

    Returns:
        List of checkpoint metadata
    """
    if checkpointer is None:
        return []

    config = create_thread_config(thread_id, checkpoint_ns)

    try:
        history = []
        async for checkpoint_tuple in checkpointer.alist(config, limit=limit):
            history.append({
                "checkpoint_id": checkpoint_tuple.checkpoint.get("id"),
                "parent_id": checkpoint_tuple.parent_config.get("configurable", {}).get("checkpoint_id") if checkpoint_tuple.parent_config else None,
                "timestamp": checkpoint_tuple.checkpoint.get("ts"),
            })
        return history

    except Exception as e:
        logger.warning(f"Failed to list thread history: {e}")
        return []


# ============================================================================
# Default Configuration
# ============================================================================

def get_default_checkpointer_config() -> dict:
    """Get default checkpointer configuration from environment.

    Returns:
        Configuration dictionary
    """
    import os

    checkpointer_type = os.getenv("LANGGRAPH_CHECKPOINTER", "memory")

    config = {
        "checkpointer_type": checkpointer_type,
    }

    if checkpointer_type == "postgres":
        config["connection_string"] = os.getenv("LANGGRAPH_POSTGRES_URI")
        config["pool_size"] = int(os.getenv("LANGGRAPH_POOL_SIZE", "5"))

    return config
