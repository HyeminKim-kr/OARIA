# ============================================================
# Multi-domain Bio NER Fine-tuning with PubMedBERT (2025 FINAL)
# BC5CDR + NCBI + JNLPBA
# Requires: datasets==2.18.0
# ============================================================

import os
import sys
import torch
import numpy as np
import datasets

from datasets import load_dataset, concatenate_datasets
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification,
    pipeline,
)
from huggingface_hub import list_datasets
from seqeval.metrics import precision_score, recall_score, f1_score
from dotenv import load_dotenv
load_dotenv()

# ------------------------------------------------------------
# 0. Hard Guard
# ------------------------------------------------------------
REQUIRED_DATASETS_VERSION = "2.18.0"

def assert_datasets_version():
    v = datasets.__version__
    if v != REQUIRED_DATASETS_VERSION:
        print("\n❌ datasets 버전이 맞지 않습니다.")
        print(f"   - 현재: datasets=={v}")
        print(f"   - 필요: datasets=={REQUIRED_DATASETS_VERSION}")
        print("\n✅ 아래 명령으로 고정하세요:")
        print("   pip uninstall datasets -y")
        print(f"   pip install datasets=={REQUIRED_DATASETS_VERSION}\n")
        sys.exit(1)

assert_datasets_version()

# ------------------------------------------------------------
# 1. Env / Config
# ------------------------------------------------------------
FAST_DEBUG = os.getenv("FAST_DEBUG", "0") == "1"

MODEL_NAME = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"
OUTPUT_DIR = os.getenv("MULTINER_OUTPUT_DIR", "./runs/pubmedbert-multiner")
HF_HUB_MODEL_ID = os.getenv("MULTINER_HUB_MODEL_ID", "user/pubmedbert-multiner")
HF_HUB_PRIVATE = os.getenv("HF_HUB_PRIVATE", "true").lower() == "true"
SEED = int(os.getenv("SEED", "42"))

if FAST_DEBUG:
    print("⚡ FAST DEBUG MODE")
    EPOCHS = 1
    BATCH_SIZE = 4
    LR = 5e-5
    MAX_SAMPLES = 100
else:
    EPOCHS = 3
    BATCH_SIZE = 8
    LR = 2e-5
    MAX_SAMPLES = None

# ------------------------------------------------------------
# 2. Unified Label Schema
# ------------------------------------------------------------
LABELS = [
    "O",
    "B-Disease", "I-Disease",
    "B-Chemical", "I-Chemical",
    "B-Gene", "I-Gene",
]

label_to_id = {l: i for i, l in enumerate(LABELS)}
id_to_label = {i: l for i, l in enumerate(LABELS)}

print("✅ Labels:", LABELS)

# ------------------------------------------------------------
# 3. Load datasets
# ------------------------------------------------------------
print("📥 Loading datasets...")

def safe_load(name):
    print(f"  - loading {name}")
    return load_dataset(name, trust_remote_code=True)

def shrink(ds):
    return ds.select(range(min(len(ds), MAX_SAMPLES)))

def require_columns(ds, name):
    cols = set(ds["train"].column_names)
    if "tokens" not in cols:
        raise RuntimeError(f"❌ {name} missing 'tokens': {cols}")
    if not (("tags" in cols) or ("ner_tags" in cols)):
        raise RuntimeError(f"❌ {name} missing 'tags/ner_tags': {cols}")

bc5cdr = safe_load("tner/bc5cdr")
ncbi = safe_load("ncbi_disease")
jnlpba = safe_load("jnlpba")

require_columns(bc5cdr, "bc5cdr")
require_columns(ncbi, "ncbi_disease")
require_columns(jnlpba, "jnlpba")

if FAST_DEBUG:
    print("⚡ FAST_DEBUG: shrinking datasets")
    def shrink(ds): return ds.select(range(min(len(ds), MAX_SAMPLES)))
    for d in [bc5cdr, ncbi, jnlpba]:
        d["train"] = shrink(d["train"])
        if "validation" in d:
            d["validation"] = shrink(d["validation"])

# ------------------------------------------------------------
# 4. Label Mapping
# ------------------------------------------------------------
BC5CDR_MAP = {
    "O": "O",
    "B-Disease": "B-Disease",
    "I-Disease": "I-Disease",
    "B-Chemical": "B-Chemical",
    "I-Chemical": "I-Chemical",
}

NCBI_MAP = {
    "O": "O",
    "B-Disease": "B-Disease",
    "I-Disease": "I-Disease",
}

JNLPBA_MAP = {
    "O": "O",
    "B-DNA": "B-Gene",
    "I-DNA": "I-Gene",
    "B-RNA": "B-Gene",
    "I-RNA": "I-Gene",
    "B-protein": "B-Gene",
    "I-protein": "I-Gene",
}

# ------------------------------------------------------------
# 5. Normalize
# ------------------------------------------------------------
def normalize(ds, mapping):
    # label id → name
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

        return {
            "tokens": ex["tokens"],
            "tags": new_tags,
        }

    return ds.map(
        convert,
        remove_columns=ds["train"].column_names
    )

def cast_tags_to_int32(ds):
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

bc5cdr = normalize(bc5cdr, BC5CDR_MAP)
ncbi   = normalize(ncbi,   NCBI_MAP)
jnlpba = normalize(jnlpba, JNLPBA_MAP)

bc5cdr = cast_tags_to_int32(bc5cdr)
ncbi   = cast_tags_to_int32(ncbi)
jnlpba = cast_tags_to_int32(jnlpba)

print(bc5cdr["train"].features)

# ------------------------------------------------------------
# 6. Merge
# ------------------------------------------------------------
train_ds = concatenate_datasets([
    bc5cdr["train"],
    ncbi["train"],
    jnlpba["train"],
]).shuffle(seed=SEED)

val_ds = concatenate_datasets([
    bc5cdr["validation"],
    ncbi["validation"],
    jnlpba["validation"],
]).shuffle(seed=SEED)

# ------------------------------------------------------------
# 7. Tokenizer
# ------------------------------------------------------------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)

def tokenize_align(examples):
    tok = tokenizer(
        examples["tokens"],
        truncation=True,
        max_length=512,
        padding="max_length" if not FAST_DEBUG else False,
        is_split_into_words=True,
    )

    labels = []
    for i, tags in enumerate(examples["tags"]):
        word_ids = tok.word_ids(batch_index=i)
        prev = None
        ids = []
        for w in word_ids:
            if w is None:
                ids.append(-100)
            elif w != prev:
                ids.append(tags[w])
            else:
                ids.append(-100)
            prev = w
        labels.append(ids)

    tok["labels"] = labels
    return tok

train_ds = train_ds.map(tokenize_align, batched=True, remove_columns=train_ds.column_names)
val_ds = val_ds.map(tokenize_align, batched=True, remove_columns=val_ds.column_names)

# ------------------------------------------------------------
# 8. Model
# ------------------------------------------------------------
model = AutoModelForTokenClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(LABELS),
    id2label=id_to_label,
    label2id=label_to_id,
)

# 🔒 PIPELINE SAFE RESET
model.config.id2label = id_to_label
model.config.label2id = label_to_id

# ------------------------------------------------------------
# 9. Metrics
# ------------------------------------------------------------
def compute_metrics(p):
    logits, labels = p
    preds = np.argmax(logits, axis=2)

    tp, tl = [], []
    for pr, la in zip(preds, labels):
        p_seq, l_seq = [], []
        for pi, li in zip(pr, la):
            if li != -100:
                p_seq.append(id_to_label[pi])
                l_seq.append(id_to_label[li])
        tp.append(p_seq)
        tl.append(l_seq)

    return {
        "precision": precision_score(tl, tp),
        "recall": recall_score(tl, tp),
        "f1": f1_score(tl, tp),
    }

# ---------------------------
# 10. Training Args (BEST PRACTICE)
# ---------------------------
if FAST_DEBUG:
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=1,
        learning_rate=LR,
        per_device_train_batch_size=BATCH_SIZE,
        seed=SEED,

        # ⛔ 디버그에서는 평가/저장 안 함
        eval_strategy="no",
        save_strategy="epoch",

        # 최소 로그
        logging_steps=10,
        report_to="none",

        # Hub (선택)
        push_to_hub=False,
    )
else:
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,

        # 로그 & 진행바
        disable_tqdm=False,
        logging_strategy="steps",
        logging_steps=50,
        log_level="info",

        # 평가 / 저장
        eval_strategy="epoch",
        save_strategy="epoch",

        # 학습 설정
        learning_rate=LR,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        weight_decay=0.01,

        # 시스템
        fp16=torch.cuda.is_available(),
        seed=SEED,
        save_total_limit=2,
        report_to="none",

        # Hub
        push_to_hub=not FAST_DEBUG,
        hub_model_id=HF_HUB_MODEL_ID,
        hub_private_repo=HF_HUB_PRIVATE,
    )

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=None if FAST_DEBUG else val_ds,
    tokenizer=tokenizer,
    data_collator=DataCollatorForTokenClassification(
        tokenizer,
        pad_to_multiple_of=8 if torch.cuda.is_available() else None
    ),
    compute_metrics=compute_metrics,
)

print("\n🚀 Training started...")
trainer.train()

# ---------------------------
# Hugging Face Hub Push
# ---------------------------
if not FAST_DEBUG:
    trainer.push_to_hub(HF_HUB_MODEL_ID, private=HF_HUB_PRIVATE)
    tokenizer.push_to_hub(HF_HUB_MODEL_ID)
    print("📦 Model pushed to Hugging Face Hub")
else:
    print("⚡ FAST_DEBUG: skip Hugging Face Hub push")
# ---------------------------🔼

print("📊 Final Evaluation:")
if not FAST_DEBUG:
    metrics = trainer.evaluate()
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")
else:
    print("⚡ FAST_DEBUG: evaluation skipped")

# ------------------------------------------------------------
# 11. Inference
# ------------------------------------------------------------
ner = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

text = "EGFR mutation is common in lung cancer treated with cisplatin."
print("\nInput:", text)
for r in ner(text):
    print(f"- {r['word']} → {r['entity_group']} ({r['score']:.3f})")

print("\n✅ DONE: Multi-domain Bio NER ready.")
