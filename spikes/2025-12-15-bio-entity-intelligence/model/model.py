"""
🧠 PubMedBERT Model Loader
==========================
Loads and configures the pre-trained model for NER fine-tuning
"""
from transformers import AutoModelForTokenClassification

from config.base import LABELS, label_to_id, id_to_label
from utils.logger import step, loading, success, stats


def load_model(model_name: str):
    """
    Load PubMedBERT model for token classification.
    
    Configures the model with BC5CDR label schema and ensures
    pipeline compatibility by resetting id2label/label2id mappings.
    
    Args:
        model_name: HuggingFace model identifier
        
    Returns:
        Configured AutoModelForTokenClassification
    """
    step("Loading pre-trained model for Token Classification", "🧠")
    loading(f"Downloading {model_name}")
    
    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=len(LABELS),
        id2label=id_to_label,
        label2id=label_to_id,
    )
    
    # ───────────────────────────────────────────────────────
    # 🔒 HARD RESET id2label / label2id for Pipeline Safety
    # This ensures the pipeline correctly maps predictions
    # ───────────────────────────────────────────────────────
    model.config.id2label = {i: label for i, label in enumerate(LABELS)}
    model.config.label2id = {label: i for i, label in enumerate(LABELS)}
    
    success("Model loaded and configured")
    stats("Model Config", {
        "Architecture": model.config.architectures[0] if model.config.architectures else "Unknown",
        "Hidden size": model.config.hidden_size,
        "Num labels": model.config.num_labels,
        "Labels": ", ".join(LABELS),
    })
    
    return model
