import os
from dotenv import load_dotenv

load_dotenv()

def get_env(key: str, default=None):
    return os.getenv(key, default)

def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean env variable (1/true/yes -> True)"""
    val = os.getenv(key, str(default)).lower()
    return val in ("1", "true", "yes")

def get_env_int(key: str, default: int) -> int:
    """Get integer env variable"""
    return int(os.getenv(key, str(default)))

def get_env_float(key: str, default: float) -> float:
    """Get float env variable"""
    return float(os.getenv(key, str(default)))

# ─────────────────────────────────────────────
# MODE: bc5cdr or multiner
# ─────────────────────────────────────────────
MODE = get_env("MODE", "bc5cdr").lower()
assert MODE in ("bc5cdr", "multiner"), f"Invalid MODE: {MODE}. Use 'bc5cdr' or 'multiner'"

# ─────────────────────────────────────────────
# FAST DEBUG
# ─────────────────────────────────────────────
FAST_DEBUG = get_env_bool("FAST_DEBUG", False)
MAX_SAMPLES = get_env_int("MAX_SAMPLES", 100) if FAST_DEBUG else None
EPOCHS = get_env_int("EPOCHS", 1 if FAST_DEBUG else 3)
BATCH_SIZE = get_env_int("BATCH_SIZE", 4 if FAST_DEBUG else 8)
LR = get_env_float("LR", 5e-5 if FAST_DEBUG else 2e-5)
SEED = get_env_int("SEED", 42)

# ─────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────
MODEL_NAME = get_env("MODEL_NAME", "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract")

# Mode-specific OUTPUT_DIR and HUB_MODEL_ID
if MODE == "bc5cdr":
    OUTPUT_DIR = get_env("BC5CDR_OUTPUT_DIR", "./runs/cancer-ner-pubmedbert")
    HUB_MODEL_ID = get_env("BC5CDR_HUB_MODEL_ID", "vparka/cancer-ner-pubmedbert")
else:  # multiner
    OUTPUT_DIR = get_env("MULTINER_OUTPUT_DIR", "./runs/pubmedbert-multiner")
    HUB_MODEL_ID = get_env("MULTINER_HUB_MODEL_ID", "vparka/pubmedbert-multiner")

# ─────────────────────────────────────────────
# HUB (optional)
# ─────────────────────────────────────────────
PUSH_TO_HUB = get_env_bool("PUSH_TO_HUB", False)
HUB_PRIVATE = get_env_bool("HF_HUB_PRIVATE", True)
