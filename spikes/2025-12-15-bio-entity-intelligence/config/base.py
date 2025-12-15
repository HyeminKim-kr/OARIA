"""
Base configuration - loaded from .env via utils/env.py
"""
from utils.env import MODEL_NAME, OUTPUT_DIR

SEED = 42

LABELS = [
    "O",
    "B-Chemical", "I-Chemical",
    "B-Disease", "I-Disease",
]

label_to_id = {l: i for i, l in enumerate(LABELS)}
id_to_label = {i: l for l, i in label_to_id.items()}

# Re-export for backward compatibility
__all__ = ["MODEL_NAME", "OUTPUT_DIR", "SEED", "LABELS", "label_to_id", "id_to_label"]
