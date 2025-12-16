"""
Base configuration - loaded from .env via utils/env.py
"""
from utils.env import MODE, MODEL_NAME, OUTPUT_DIR, HUB_MODEL_ID, SEED

# Mode-based LABELS
if MODE == "bc5cdr":
    LABELS = [
        "O",
        "B-Chemical", "I-Chemical",
        "B-Disease", "I-Disease",
    ]
else:  # multiner
    LABELS = [
        "O",
        "B-Disease", "I-Disease",
        "B-Chemical", "I-Chemical",
        "B-Gene", "I-Gene",
    ]

label_to_id = {l: i for i, l in enumerate(LABELS)}
id_to_label = {i: l for l, i in label_to_id.items()}

# Re-export for backward compatibility
__all__ = ["MODE", "MODEL_NAME", "OUTPUT_DIR", "HUB_MODEL_ID", "SEED", "LABELS", "label_to_id", "id_to_label"]
