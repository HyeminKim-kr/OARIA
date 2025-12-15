"""
🔤 Tokenizer Loader
===================
Loads the PubMedBERT tokenizer for NER preprocessing
"""
from transformers import AutoTokenizer

from config.base import MODEL_NAME
from utils.logger import step, loading, success


def load_tokenizer():
    """
    Load the fast tokenizer for PubMedBERT.
    
    Returns:
        AutoTokenizer configured for the model
    """
    step("Loading tokenizer", "🔤")
    loading(f"Initializing {MODEL_NAME} tokenizer")
    
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        use_fast=True,
    )
    
    success("Tokenizer ready")
    return tokenizer
