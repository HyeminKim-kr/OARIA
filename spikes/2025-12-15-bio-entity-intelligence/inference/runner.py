"""
🧪 Inference Runner
===================
Run NER inference on sample texts with colorful output
"""
from transformers import pipeline

from utils.logger import phase, step, loading, success, result, section


def create_ner_pipeline(model, tokenizer):
    """
    Create a NER pipeline for inference.
    
    Args:
        model: Fine-tuned model
        tokenizer: Tokenizer
        
    Returns:
        HuggingFace NER pipeline
    """
    step("Creating NER inference pipeline", "🔧")
    loading("Initializing pipeline")
    
    ner_pipeline = pipeline(
        "ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",
    )
    
    success("Pipeline ready for inference")
    return ner_pipeline


def run_inference_test(model, tokenizer, texts: list[str] = None):
    """
    Run inference tests on sample biomedical texts.
    
    Args:
        model: Fine-tuned model
        tokenizer: Tokenizer
        texts: Optional list of texts to test
    """
    phase("INFERENCE TEST", "Validating model predictions")
    
    if texts is None:
        texts = [
            "EGFR mutation is common in lung cancer treated with cisplatin.",
            "Metformin is used to treat type 2 diabetes mellitus.",
            "Ibuprofen can cause gastrointestinal bleeding.",
        ]
    
    ner = create_ner_pipeline(model, tokenizer)
    
    for i, text in enumerate(texts, 1):
        section(f"Test {i}")
        print(f"   📝 Input: {text}")
        print()
        
        entities = ner(text)
        
        if entities:
            print("   🧬 Detected Entities:")
            for entity in entities:
                result(
                    entity=entity["word"],
                    label=entity["entity_group"],
                    score=entity["score"],
                )
        else:
            print("   ⚠️  No entities detected")
        print()
    
    success("Inference tests completed!")
