"""
📊 Training Metrics
===================
SeqEval-compatible metrics for NER evaluation
"""
import numpy as np
from seqeval.metrics import precision_score, recall_score, f1_score

from config.base import id_to_label
from utils.logger import stats


def compute_metrics(eval_pred):
    """
    Compute precision, recall, and F1 score using seqeval.
    
    Converts model predictions to BIO-tagged sequences
    and computes entity-level metrics.
    
    Args:
        eval_pred: (logits, labels) tuple from Trainer
        
    Returns:
        Dict with precision, recall, and f1 scores
    """
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

    precision = precision_score(true_labels, true_preds, zero_division=0)
    recall = recall_score(true_labels, true_preds, zero_division=0)
    f1 = f1_score(true_labels, true_preds, zero_division=0)
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
