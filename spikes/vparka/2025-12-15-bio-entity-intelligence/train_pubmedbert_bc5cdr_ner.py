# ============================================================
# Cancer NER Fine-tuning with PubMedBERT (2025 FINAL - WORKING)
# Dataset: tner/bc5cdr (script-based) -> requires datasets==2.18.0
# ============================================================

import os
import sys
import torch
import numpy as np

import datasets
from transformers import DataCollatorForTokenClassification
from datasets import load_dataset

from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    pipeline,
)

from seqeval.metrics import precision_score, recall_score, f1_score
from dotenv import load_dotenv
load_dotenv()

# ---------------------------
# 0. Hard Guard (Version Pin)
# ---------------------------
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

# ---------------------------
# 1. Env / Config
# ---------------------------
FAST_DEBUG = os.getenv("FAST_DEBUG", "0") == "1"

MODEL_NAME = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"
OUTPUT_DIR = os.getenv(
    "OUTPUT_DIR",
    "./cancer-ner-pubmedbert"
)
HF_HUB_MODEL_ID = os.getenv(
    "HF_HUB_MODEL_ID",
    "vparka/cancer-ner-pubmedbert"
)

HF_HUB_PRIVATE = os.getenv(
    "HF_HUB_PRIVATE",
    "true"
).lower() == "true"

SEED = int(os.getenv("SEED", "42"))

if FAST_DEBUG:
    print("⚡ FAST DEBUG MODE (≈1 minute run)")
    EPOCHS = 1
    BATCH_SIZE = 4
    LR = 5e-5
    MAX_SAMPLES = 100
else:
    EPOCHS = 3
    BATCH_SIZE = 8
    LR = 2e-5
    MAX_SAMPLES = None


# ---------------------------
# 2. Load Dataset (BC5CDR)
#   ✅ datasets==2.18.0 에서만 동작
# ---------------------------
print("📥 Loading BC5CDR dataset (tner/bc5cdr)...")
dataset = load_dataset("tner/bc5cdr", trust_remote_code=True)

# ---------------------------
# 3. Labels (BC5CDR fixed schema)
# ---------------------------
label_list = [
    "O",
    "B-Chemical",
    "I-Chemical",
    "B-Disease",
    "I-Disease",
]

label_to_id = {l: i for i, l in enumerate(label_list)}
id_to_label = {i: l for l, i in enumerate(label_list)}

print("✅ Labels:", label_list)

# ---------------------------
# 4. Tokenizer
# ---------------------------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)

def tokenize_and_align_labels(examples):
    tokenized = tokenizer(
        examples["tokens"],
        truncation=True,
        max_length=512,
        padding=True,
        is_split_into_words=True
    )

    labels = []
    for i, label_seq in enumerate(examples["tags"]):
        word_ids = tokenized.word_ids(batch_index=i)
        prev = None
        ids = []
        for w in word_ids:
            if w is None:
                ids.append(-100)
            elif w != prev:
                ids.append(label_seq[w])
            else:
                # subword는 loss 계산 제외
                ids.append(-100)
            prev = w
        labels.append(ids)

    tokenized["labels"] = labels
    return tokenized

print("🔄 Tokenizing...")
tokenized_dataset = dataset.map(
    tokenize_and_align_labels,
    batched=True,
    remove_columns=dataset["train"].column_names,
)

# ---------------------------
# FAST DEBUG: shrink dataset
# ---------------------------
if FAST_DEBUG:
    print("⚡ FAST_DEBUG: reducing dataset size")
    tokenized_dataset["train"] = tokenized_dataset["train"].select(range(MAX_SAMPLES))
    tokenized_dataset["validation"] = tokenized_dataset["validation"].select(range(MAX_SAMPLES))

# ---------------------------
# 5. Model
# ---------------------------
print("🧠 Loading PubMedBERT model...")
model = AutoModelForTokenClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(label_list),
    id2label=id_to_label,
    label2id=label_to_id
)

# ---------------------------
# 🔒 HARD RESET id2label / label2id (PIPELINE SAFE)
# ---------------------------
model.config.id2label = {i: label for i, label in enumerate(label_list)}
model.config.label2id = {label: i for i, label in enumerate(label_list)}

# ---------------------------
# 6. Metrics (SAFE + SEQEVAL COMPATIBLE)
# ---------------------------
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=2)

    true_preds, true_labels = [], []
    for p, l in zip(preds, labels):
        tp, tl = [], []
        for pi, li in zip(p, l):
            if li == -100:
                continue
            tp.append(id_to_label.get(int(pi), "O"))
            tl.append(id_to_label.get(int(li), "O"))
        if tp:
            true_preds.append(tp)
            true_labels.append(tl)

    return {
        "precision": precision_score(true_labels, true_preds),
        "recall": recall_score(true_labels, true_preds),
        "f1": f1_score(true_labels, true_preds),
    }

# ---------------------------
# 6. Training Args (Progress + Logs)
# ---------------------------
if FAST_DEBUG:
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=1,
        learning_rate=LR,
        per_device_train_batch_size=BATCH_SIZE,
        seed=SEED,

        # ⛔ eval / save 완전 제거
        eval_strategy="no",
        save_strategy="epoch",

        # logging 최소
        logging_steps=10,
        report_to="none",

        # 🔑 Hub 설정
        push_to_hub=not FAST_DEBUG,
        hub_model_id=HF_HUB_MODEL_ID,
        hub_private_repo=HF_HUB_PRIVATE,
    )
else:
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,

        # 🔥 Progress & Logging
        disable_tqdm=False,
        logging_strategy="steps",
        logging_steps=50,
        log_level="info",

        # Evaluation / Save
        eval_strategy="epoch",
        save_strategy="epoch",

        # Training config
        learning_rate=LR,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=EPOCHS,
        weight_decay=0.01,

        # System
        fp16=torch.cuda.is_available(),
        seed=SEED,
        save_total_limit=2,
        report_to="none",

        # 🔑 Hub 설정
        push_to_hub=not FAST_DEBUG,
        hub_model_id=HF_HUB_MODEL_ID,
        hub_private_repo=HF_HUB_PRIVATE,
    )

data_collator = DataCollatorForTokenClassification(tokenizer)

# ---------------------------
# 7. Trainer
# ---------------------------
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    eval_dataset=tokenized_dataset["validation"],
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics
)

# ---------------------------
# 8. Train
# ---------------------------
print("🚀 Training started...")
trainer.train()

# ---------------------------
# Hugging Face Hub Push
# ---------------------------
trainer.push_to_hub(HF_HUB_MODEL_ID)
tokenizer.push_to_hub(HF_HUB_MODEL_ID)

if not FAST_DEBUG:
    trainer.push_to_hub(HF_HUB_MODEL_ID, private=HF_HUB_PRIVATE)
    tokenizer.push_to_hub(HF_HUB_MODEL_ID)

print("📦 Model pushed to Hugging Face Hub")
# ---------------------------🔼

print("📊 Final Evaluation:")
if not FAST_DEBUG:
    metrics = trainer.evaluate()
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")
else:
    print("⚡ FAST_DEBUG: evaluation skipped")

# ---------------------------
# 9. Inference Test
# ---------------------------
print("🧪 Running inference test...")

ner = pipeline(
    "ner",
    model=model,
    tokenizer=tokenizer,
    aggregation_strategy="simple"
)

text = "EGFR mutation is common in lung cancer treated with cisplatin."
print("\n🔍 Input:", text)
print("\n🧬 NER Output:")
for r in ner(text):
    print(f"- {r['word']} → {r['entity_group']} (score={r['score']:.3f})")

print("\n✅ DONE: Cancer NER model ready.")
