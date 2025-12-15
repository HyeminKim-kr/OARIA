"""
📥 Data Loader for BC5CDR Dataset
==================================
Loads and tokenizes the BC5CDR NER dataset for training
"""
from datasets import load_dataset
from transformers import AutoTokenizer

from config.base import MODEL_NAME
from config.train import FAST_DEBUG, MAX_SAMPLES
from utils.logger import (
    phase, step, loading, success, stats, warning
)


def tokenize_and_align_labels(examples, tokenizer):
    """
    Tokenize examples and align NER labels with subword tokens.
    Subwords are marked with -100 to exclude from loss computation.
    """
    tokenized = tokenizer(
        examples["tokens"],
        truncation=True,
        max_length=512,
        padding=True,
        is_split_into_words=True,
    )

    labels = []
    for i, tag_seq in enumerate(examples["tags"]):
        word_ids = tokenized.word_ids(batch_index=i)
        prev = None
        ids = []
        for w in word_ids:
            if w is None:
                ids.append(-100)
            elif w != prev:
                ids.append(tag_seq[w])
            else:
                # Subword → exclude from loss
                ids.append(-100)
            prev = w
        labels.append(ids)

    tokenized["labels"] = labels
    return tokenized


def load_bc5cdr():
    """
    Load and preprocess the BC5CDR dataset.
    
    Returns:
        DatasetDict with train/validation splits, tokenized and ready for training
    """
    phase("DATA LOADING", "BC5CDR Named Entity Recognition Dataset")
    
    # ───────────────────────────────────────────────────────
    # Step 1: Load raw dataset
    # ───────────────────────────────────────────────────────
    step("Loading BC5CDR dataset from HuggingFace Hub", "📥")
    loading("Downloading tner/bc5cdr")
    
    dataset = load_dataset("tner/bc5cdr", trust_remote_code=True)
    
    success("Dataset loaded successfully")
    stats("Dataset Info", {
        "Train samples": len(dataset["train"]),
        "Validation samples": len(dataset["validation"]),
        "Test samples": len(dataset.get("test", [])) or "N/A",
    })
    
    # ───────────────────────────────────────────────────────
    # Step 2: Initialize tokenizer
    # ───────────────────────────────────────────────────────
    step("Initializing tokenizer for alignment", "🔤")
    loading(f"Loading {MODEL_NAME} tokenizer")
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    
    success("Tokenizer ready")
    
    # ───────────────────────────────────────────────────────
    # Step 3: Tokenize and align labels
    # ───────────────────────────────────────────────────────
    step("Tokenizing and aligning NER labels", "🔄")
    loading("Processing dataset with subword alignment")
    
    tokenized_dataset = dataset.map(
        lambda examples: tokenize_and_align_labels(examples, tokenizer),
        batched=True,
        remove_columns=dataset["train"].column_names,
        desc="Tokenizing",
    )
    
    success("Tokenization complete")
    
    # ───────────────────────────────────────────────────────
    # Step 4: Apply FAST_DEBUG sample reduction
    # ───────────────────────────────────────────────────────
    if FAST_DEBUG:
        step("Reducing dataset for FAST_DEBUG mode", "⚡")
        warning(f"FAST_DEBUG active: limiting to {MAX_SAMPLES} samples")
        
        tokenized_dataset["train"] = tokenized_dataset["train"].select(
            range(min(MAX_SAMPLES, len(tokenized_dataset["train"])))
        )
        tokenized_dataset["validation"] = tokenized_dataset["validation"].select(
            range(min(MAX_SAMPLES, len(tokenized_dataset["validation"])))
        )
        
        stats("Reduced Dataset", {
            "Train samples": len(tokenized_dataset["train"]),
            "Validation samples": len(tokenized_dataset["validation"]),
        })
    
    success("Data preparation complete!")
    return tokenized_dataset
