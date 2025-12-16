"""
🏋️ Training Trainer Builder
=============================
Configures and builds the HuggingFace Trainer
"""
import torch
from transformers import Trainer, TrainingArguments

from config import train as train_config
from config import hub as hub_config
from config.base import SEED
from training.metrics import compute_metrics
from training.callbacks import TrainStartCallback, TrainEndCallback, EpochCallback
from utils.logger import phase, step, loading, success, stats, box


def build_trainer(
    model,
    tokenizer,
    train_dataset,
    eval_dataset,
    data_collator,
    output_dir: str,
):
    """
    Build a configured HuggingFace Trainer.
    
    Args:
        model: The model to train
        tokenizer: Tokenizer for the model
        train_dataset: Training dataset
        eval_dataset: Evaluation dataset
        data_collator: Data collator for batching
        output_dir: Output directory for checkpoints
        
    Returns:
        Configured Trainer instance
    """
    phase("TRAINING SETUP", "Configuring Trainer with optimal settings")
    
    # ───────────────────────────────────────────────────────
    # Step 1: Configure training arguments
    # ───────────────────────────────────────────────────────
    step("Configuring training arguments", "⚙️")
    
    if train_config.FAST_DEBUG:
        args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=train_config.EPOCHS,
            learning_rate=train_config.LR,
            per_device_train_batch_size=train_config.BATCH_SIZE,
            seed=SEED,
            
            # Minimal eval/save for debug
            eval_strategy="no",
            save_strategy="epoch",
            logging_steps=10,
            report_to="none",
            
            # Hub settings
            push_to_hub=hub_config.PUSH_TO_HUB,
            hub_model_id=hub_config.HUB_MODEL_ID,
            hub_private_repo=hub_config.HUB_PRIVATE,
        )
    else:
        args = TrainingArguments(
            output_dir=output_dir,
            
            # Progress & Logging
            disable_tqdm=False,
            logging_strategy="steps",
            logging_steps=50,
            log_level="info",
            
            # Evaluation / Save
            eval_strategy="epoch",
            save_strategy="epoch",
            
            # Training config
            learning_rate=train_config.LR,
            per_device_train_batch_size=train_config.BATCH_SIZE,
            per_device_eval_batch_size=train_config.BATCH_SIZE,
            num_train_epochs=train_config.EPOCHS,
            weight_decay=0.01,
            
            # System
            fp16=torch.cuda.is_available(),
            seed=SEED,
            save_total_limit=2,
            report_to="none",
            
            # Hub settings
            push_to_hub=hub_config.PUSH_TO_HUB,
            hub_model_id=hub_config.HUB_MODEL_ID,
            hub_private_repo=hub_config.HUB_PRIVATE,
        )
    
    box("Training Config", [
        f"Epochs       : {train_config.EPOCHS}",
        f"Batch Size   : {train_config.BATCH_SIZE}",
        f"Learning Rate: {train_config.LR}",
        f"FP16         : {args.fp16}",
        f"Push to Hub  : {hub_config.PUSH_TO_HUB}",
        f"FAST_DEBUG   : {train_config.FAST_DEBUG}",
    ])
    
    # ───────────────────────────────────────────────────────
    # Step 2: Initialize Trainer
    # ───────────────────────────────────────────────────────
    step("Initializing Trainer with callbacks", "🏋️")
    loading("Building trainer")
    
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[
            TrainStartCallback(),
            TrainEndCallback(),
            EpochCallback(),
        ],
    )
    
    success("Trainer ready!")
    stats("Trainer Info", {
        "Train samples": len(train_dataset),
        "Eval samples": len(eval_dataset),
        "Total steps": trainer.args.max_steps if trainer.args.max_steps > 0 else "auto",
    })
    
    return trainer
