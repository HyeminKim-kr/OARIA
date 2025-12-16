"""
HuggingFace Hub configuration - loaded from .env via utils/env.py
"""
from utils.env import (
    PUSH_TO_HUB,
    HUB_MODEL_ID,
    HUB_PRIVATE,
)

# Re-export for backward compatibility
__all__ = ["PUSH_TO_HUB", "HUB_MODEL_ID", "HUB_PRIVATE"]
