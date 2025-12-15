"""
📣 Training Callbacks
=====================
Custom callbacks for colorful training progress logging
"""
from transformers import TrainerCallback
from utils.logger import phase, success, stats, step


class TrainStartCallback(TrainerCallback):
    """Callback for training start event."""
    
    def on_train_begin(self, args, state, control, **kwargs):
        phase("TRAINING", "Fine-tuning PubMedBERT on BC5CDR")
        step("Starting training loop", "🚀")


class TrainEndCallback(TrainerCallback):
    """Callback for training end event."""
    
    def on_train_end(self, args, state, control, **kwargs):
        success("Training completed!")
        stats("Final Training Stats", {
            "Total epochs": state.epoch,
            "Total steps": state.global_step,
            "Best metric": f"{state.best_metric:.4f}" if state.best_metric else "N/A",
        })


class EpochCallback(TrainerCallback):
    """Callback for epoch completion events."""
    
    def on_epoch_end(self, args, state, control, **kwargs):
        epoch_num = int(state.epoch)
        step(f"Epoch {epoch_num}/{int(args.num_train_epochs)} completed", "📈")


class EvalCallback(TrainerCallback):
    """Callback for evaluation events."""
    
    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            step("Evaluation completed", "📊")
            stats("Eval Results", {
                "Loss": f"{metrics.get('eval_loss', 'N/A'):.4f}",
                "Precision": f"{metrics.get('eval_precision', 'N/A'):.4f}",
                "Recall": f"{metrics.get('eval_recall', 'N/A'):.4f}",
                "F1": f"{metrics.get('eval_f1', 'N/A'):.4f}",
            })
