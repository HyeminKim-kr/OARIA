"""
Training configuration - loaded from .env via utils/env.py
"""
from utils.env import (
    FAST_DEBUG,
    EPOCHS,
    BATCH_SIZE,
    LR,
    MAX_SAMPLES,
)

# Re-export for backward compatibility
__all__ = ["FAST_DEBUG", "EPOCHS", "BATCH_SIZE", "LR", "MAX_SAMPLES"]
