"""
🧬 BIO-ENTITY NER FINE-TUNING PIPELINE
======================================
Main entry point for the Cancer NER fine-tuning with PubMedBERT

Dataset: tner/bc5cdr (requires datasets==2.18.0)
Model: microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract
"""
from transformers import DataCollatorForTokenClassification

# ───────────────────────────────────────────────────────
# Utils & Config
# ───────────────────────────────────────────────────────
from utils.logger import (
    banner, phase, step, loading, success, done, warning, box, reset_steps
)
from utils.version import check_all_versions

from config import base as base_config
from config import train as train_config
from config import hub as hub_config

# ───────────────────────────────────────────────────────
# Pipeline Modules
# ───────────────────────────────────────────────────────
from data.loader import load_bc5cdr
from model.model import load_model
from model.tokenizer import load_tokenizer
from training.trainer import build_trainer
from inference.runner import run_inference_test


def main():
    """
    Main pipeline orchestrating the full NER fine-tuning workflow.
    
    Phases:
        1. Initialization & Version Check
        2. Data Loading & Preprocessing
        3. Model & Tokenizer Loading
        4. Trainer Setup & Training
        5. Hub Push (optional)
        6. Evaluation & Inference Test
    """
    # ═══════════════════════════════════════════════════════
    # PHASE 0: Startup
    # ═══════════════════════════════════════════════════════
    banner()
    reset_steps()
    
    box("Configuration", [
        f"Model     : {base_config.MODEL_NAME}",
        f"Labels    : {len(base_config.LABELS)} classes",
        f"Epochs    : {train_config.EPOCHS}",
        f"Batch Size: {train_config.BATCH_SIZE}",
        f"FAST_DEBUG: {train_config.FAST_DEBUG}",
    ])
    
    if train_config.FAST_DEBUG:
        warning("⚡ FAST_DEBUG 모드 활성화 - 빠른 테스트 실행")
    
    # ═══════════════════════════════════════════════════════
    # PHASE 1: Version Check
    # ═══════════════════════════════════════════════════════
    phase("VERSION CHECK", "Validating dependencies")
    step("Checking datasets version", "🔍")
    check_all_versions()
    
    # ═══════════════════════════════════════════════════════
    # PHASE 2: Data Loading
    # ═══════════════════════════════════════════════════════
    dataset = load_bc5cdr()
    
    # ═══════════════════════════════════════════════════════
    # PHASE 3: Model & Tokenizer
    # ═══════════════════════════════════════════════════════
    phase("MODEL LOADING", "Loading PubMedBERT for NER")
    tokenizer = load_tokenizer()
    model = load_model(base_config.MODEL_NAME)
    
    # ═══════════════════════════════════════════════════════
    # PHASE 4: Trainer Setup
    # ═══════════════════════════════════════════════════════
    collator = DataCollatorForTokenClassification(tokenizer)
    
    trainer = build_trainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        data_collator=collator,
        output_dir=base_config.OUTPUT_DIR,
    )
    
    # ═══════════════════════════════════════════════════════
    # PHASE 5: Training
    # ═══════════════════════════════════════════════════════
    trainer.train()
    
    # ═══════════════════════════════════════════════════════
    # PHASE 6: Evaluation
    # ═══════════════════════════════════════════════════════
    phase("EVALUATION", "Final model evaluation")
    step("Running evaluation on validation set", "📊")
    eval_results = trainer.evaluate()
    
    box("Final Metrics", [
        f"Loss      : {eval_results.get('eval_loss', 'N/A'):.4f}",
        f"Precision : {eval_results.get('eval_precision', 'N/A'):.4f}",
        f"Recall    : {eval_results.get('eval_recall', 'N/A'):.4f}",
        f"F1 Score  : {eval_results.get('eval_f1', 'N/A'):.4f}",
    ])
    
    # ═══════════════════════════════════════════════════════
    # PHASE 7: Hub Push
    # ═══════════════════════════════════════════════════════
    if train_config.FAST_DEBUG:
        warning("FAST_DEBUG mode: Hub push 건너뜀")
    else:
        phase("HUB PUSH", "Uploading to HuggingFace Hub")
        step(f"Pushing model to {hub_config.HUB_MODEL_ID}", "📤")
        loading("Uploading model and tokenizer")
        
        # Note: private 설정은 TrainingArguments의 hub_private_repo에서 설정
        trainer.push_to_hub(hub_config.HUB_MODEL_ID)
        tokenizer.push_to_hub(hub_config.HUB_MODEL_ID)
        
        success(f"Model published: {hub_config.HUB_MODEL_ID}")
    
    # ═══════════════════════════════════════════════════════
    # PHASE 8: Inference Test
    # ═══════════════════════════════════════════════════════
    run_inference_test(model, tokenizer)
    
    # ═══════════════════════════════════════════════════════
    # COMPLETE!
    # ═══════════════════════════════════════════════════════
    done("🎉 Cancer NER Fine-tuning Pipeline Complete!")
    box("Summary", [
        "✅ Model trained successfully",
        "✅ Evaluation metrics computed",
        f"✅ Model ready at: {hub_config.HUB_MODEL_ID}" if not train_config.FAST_DEBUG else "⚡ FAST_DEBUG run complete",
    ])


if __name__ == "__main__":
    main()
