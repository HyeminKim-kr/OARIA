"""
📥 Data Loader for Bio-Entity NER
==================================
Loads and tokenizes NER datasets based on MODE:
- bc5cdr: BC5CDR dataset (Chemical + Disease)
- multiner: BC5CDR + NCBI Disease + JNLPBA (Chemical + Disease + Gene)
"""
import numpy as np
import datasets
from datasets import load_dataset, concatenate_datasets
from transformers import AutoTokenizer

from config.base import MODE, MODEL_NAME, LABELS, label_to_id
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


# ─────────────────────────────────────────────
# MULTINER: Label Mapping for dataset merging
# ─────────────────────────────────────────────
BC5CDR_MAP = {
    "O": "O",
    "B-Disease": "B-Disease", "I-Disease": "I-Disease",
    "B-Chemical": "B-Chemical", "I-Chemical": "I-Chemical",
}

NCBI_MAP = {
    "O": "O",
    "B-Disease": "B-Disease", "I-Disease": "I-Disease",
}

JNLPBA_MAP = {
    "O": "O",
    "B-DNA": "B-Gene", "I-DNA": "I-Gene",
    "B-RNA": "B-Gene", "I-RNA": "I-Gene",
    "B-protein": "B-Gene", "I-protein": "I-Gene",
}


def normalize_dataset(ds, mapping):
    """Normalize dataset labels to unified schema."""
    if "tags" in ds["train"].features:
        feature = ds["train"].features["tags"].feature
    else:
        feature = ds["train"].features["ner_tags"].feature

    id2label = feature.names if hasattr(feature, "names") else None

    def convert(ex):
        raw_tags = ex["tags"] if "tags" in ex else ex["ner_tags"]
        new_tags = []
        for t in raw_tags:
            if id2label and t < len(id2label):
                label = id2label[t]
            else:
                label = "O"
            mapped = mapping.get(label, "O")
            new_tags.append(label_to_id[mapped])
        return {"tokens": ex["tokens"], "tags": new_tags}

    return ds.map(convert, remove_columns=ds["train"].column_names)


def cast_tags_to_int32(ds):
    """Cast tags to int32 for concatenation compatibility."""
    def cast(ex):
        return {
            "tokens": ex["tokens"],
            "tags": np.array(ex["tags"], dtype=np.int32),
        }
    return ds.map(
        cast,
        features=datasets.Features({
            "tokens": datasets.Sequence(datasets.Value("string")),
            "tags": datasets.Sequence(datasets.Value("int32")),
        })
    )


def shrink_dataset(ds, max_samples):
    """Reduce dataset size for fast debugging."""
    return ds.select(range(min(len(ds), max_samples)))


def load_bc5cdr_only(tokenizer):
    """Load BC5CDR dataset only."""
    step("Loading BC5CDR dataset from HuggingFace Hub", "📥")
    loading("Downloading tner/bc5cdr")
    
    dataset = load_dataset("tner/bc5cdr", trust_remote_code=True)
    
    success("Dataset loaded successfully")
    stats("Dataset Info", {
        "Train samples": len(dataset["train"]),
        "Validation samples": len(dataset["validation"]),
    })
    
    return dataset


def load_multiner_merged(tokenizer, seed=42):
    """Load and merge BC5CDR + NCBI + JNLPBA datasets."""
    step("Loading multi-domain datasets", "📥")
    
    loading("Downloading tner/bc5cdr")
    bc5cdr = load_dataset("tner/bc5cdr", trust_remote_code=True)
    success("BC5CDR loaded")
    
    loading("Downloading ncbi_disease")
    ncbi = load_dataset("ncbi_disease", trust_remote_code=True)
    success("NCBI Disease loaded")
    
    loading("Downloading jnlpba")
    jnlpba = load_dataset("jnlpba", trust_remote_code=True)
    success("JNLPBA loaded")
    
    step("Normalizing label schemas", "🔄")
    
    bc5cdr = normalize_dataset(bc5cdr, BC5CDR_MAP)
    ncbi = normalize_dataset(ncbi, NCBI_MAP)
    jnlpba = normalize_dataset(jnlpba, JNLPBA_MAP)
    
    bc5cdr = cast_tags_to_int32(bc5cdr)
    ncbi = cast_tags_to_int32(ncbi)
    jnlpba = cast_tags_to_int32(jnlpba)
    
    step("Merging datasets", "🔗")
    
    train_ds = concatenate_datasets([
        bc5cdr["train"],
        ncbi["train"],
        jnlpba["train"],
    ]).shuffle(seed=seed)
    
    val_ds = concatenate_datasets([
        bc5cdr["validation"],
        ncbi["validation"],
        jnlpba["validation"],
    ]).shuffle(seed=seed)
    
    # Create DatasetDict-like structure
    dataset = datasets.DatasetDict({
        "train": train_ds,
        "validation": val_ds,
    })
    
    success("Datasets merged successfully")
    stats("Merged Dataset Info", {
        "Train samples": len(dataset["train"]),
        "Validation samples": len(dataset["validation"]),
    })
    
    return dataset


def load_dataset_by_mode():
    """
    Load dataset based on MODE environment variable.
    
    Returns:
        DatasetDict with train/validation splits, tokenized and ready for training
    """
    phase("DATA LOADING", f"{MODE.upper()} Named Entity Recognition Dataset")
    
    step(f"Mode: {MODE.upper()}", "🎯")
    stats("Labels", {"Count": len(LABELS), "Labels": ", ".join(LABELS)})
    
    # ───────────────────────────────────────────────────────
    # Step 1: Initialize tokenizer
    # ───────────────────────────────────────────────────────
    step("Initializing tokenizer for alignment", "🔤")
    loading(f"Loading {MODEL_NAME} tokenizer")
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    success("Tokenizer ready")
    
    # ───────────────────────────────────────────────────────
    # Step 2: Load raw dataset based on mode
    # ───────────────────────────────────────────────────────
    if MODE == "bc5cdr":
        dataset = load_bc5cdr_only(tokenizer)
    else:  # multiner
        from utils.env import SEED
        dataset = load_multiner_merged(tokenizer, seed=SEED)
    
    # ───────────────────────────────────────────────────────
    # Step 3: Apply FAST_DEBUG sample reduction (before tokenization)
    # ───────────────────────────────────────────────────────
    if FAST_DEBUG:
        step("Reducing dataset for FAST_DEBUG mode", "⚡")
        warning(f"FAST_DEBUG active: limiting to {MAX_SAMPLES} samples")
        
        dataset["train"] = shrink_dataset(dataset["train"], MAX_SAMPLES)
        dataset["validation"] = shrink_dataset(dataset["validation"], MAX_SAMPLES)
    
    # ───────────────────────────────────────────────────────
    # Step 4: Tokenize and align labels
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
    
    if FAST_DEBUG:
        stats("Final Dataset", {
            "Train samples": len(tokenized_dataset["train"]),
            "Validation samples": len(tokenized_dataset["validation"]),
        })
    
    success("Data preparation complete!")
    return tokenized_dataset


# Backward compatibility alias
def load_bc5cdr():
    """Backward compatible function (always loads based on MODE)."""
    return load_dataset_by_mode()
