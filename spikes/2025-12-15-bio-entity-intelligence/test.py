"""
🧪 NER Model Comparison Test
============================
Compare multiple NER models side by side with beautiful logging
"""
from transformers import pipeline

from utils.logger import (
    banner, phase, section, box, step, success, warning, 
    loading, done, stats, result, reset_steps
)

# ---------------------------
# 분석할 텍스트 예시 10개 (의미 포함)
# ---------------------------
test_sentences = [
    {
        "text": "EGFR mutation is common in lung cancer treated with cisplatin.",
        "meaning": "EGFR 유전자 돌연변이는 시스플라틴으로 치료받는 폐암에서 흔하다."
    },
    {
        "text": "BRCA1 and BRCA2 mutations increase the risk of breast and ovarian cancer.",
        "meaning": "BRCA1과 BRCA2 유전자 돌연변이는 유방암과 난소암의 위험을 증가시킨다."
    },
    {
        "text": "TP53 is one of the most frequently mutated genes in human cancers.",
        "meaning": "TP53은 인간 암에서 가장 빈번하게 돌연변이가 발생하는 유전자 중 하나다."
    },
    {
        "text": "HER2-positive breast cancer patients often respond to trastuzumab.",
        "meaning": "HER2 양성 유방암 환자들은 종종 트라스투주맙 치료에 반응한다."
    },
    {
        "text": "KRAS mutations are associated with poor prognosis in colorectal cancer.",
        "meaning": "KRAS 돌연변이는 대장암에서 나쁜 예후와 연관되어 있다."
    },
    {
        "text": "BRAF V600E mutation is detected in melanoma patients.",
        "meaning": "BRAF V600E 돌연변이는 흑색종 환자에서 검출된다."
    },
    {
        "text": "PD-1 inhibitors improve survival in advanced lung cancer.",
        "meaning": "PD-1 억제제는 진행성 폐암에서 생존율을 향상시킨다."
    },
    {
        "text": "ALK rearrangements define a distinct subtype of non-small cell lung cancer.",
        "meaning": "ALK 재배열은 비소세포 폐암의 특정 아형을 정의한다."
    },
    {
        "text": "Temozolomide is commonly used to treat glioblastoma.",
        "meaning": "테모졸로마이드는 교모세포종 치료에 흔히 사용된다."
    },
    {
        "text": "Mutations in PIK3CA activate the PI3K signaling pathway in cancer.",
        "meaning": "PIK3CA 돌연변이는 암에서 PI3K 신호 전달 경로를 활성화한다."
    },
]

# ---------------------------
# 비교할 모델 리스트
# ---------------------------
models_to_compare = [
    {
        "name": "General Bio-NER (d4data)",
        "id": "d4data/biomedical-ner-all"
    },
    {
        "name": "Cancer Specific NER (VParka)",
        "id": "VParka/cancer-ner-pubmedbert"
    }
]


def main():
    # ═══════════════════════════════════════════════════════
    # Startup
    # ═══════════════════════════════════════════════════════
    banner()
    reset_steps()
    
    box("Test Configuration", [
        f"Test sentences: {len(test_sentences)}",
        f"Models to compare: {len(models_to_compare)}",
    ])
    
    # ═══════════════════════════════════════════════════════
    # Load Models
    # ═══════════════════════════════════════════════════════
    phase("MODEL LOADING", "Loading NER pipelines for comparison")
    
    pipelines = {}
    for model_info in models_to_compare:
        step(f"Loading {model_info['name']}", "🧠")
        loading(f"Downloading {model_info['id']}")
        
        ner = pipeline(
            "ner",
            model=model_info["id"],
            aggregation_strategy="simple"
        )
        pipelines[model_info["name"]] = ner
        success(f"{model_info['name']} loaded")
    
    # ═══════════════════════════════════════════════════════
    # Run Tests
    # ═══════════════════════════════════════════════════════
    phase("INFERENCE TEST", "Running NER on test sentences")
    
    for idx, item in enumerate(test_sentences, 1):
        text = item["text"]
        meaning = item["meaning"]
        
        section(f"Test {idx}/{len(test_sentences)}")
        step(f"Input: {text}", "🧪")
        stats("Sentence Info", {
            "English": text,
            "Korean": meaning,
        })
        
        for model_name, ner_pipeline in pipelines.items():
            step(f"Running {model_name}", "▶")
            
            results = ner_pipeline(text)
            
            if not results:
                warning("No entities detected")
            else:
                for r in results:
                    result(
                        entity=r['word'],
                        label=r['entity_group'],
                        score=r['score']
                    )
    
    # ═══════════════════════════════════════════════════════
    # Complete
    # ═══════════════════════════════════════════════════════
    done("🎉 NER Model Comparison Complete!")
    box("Summary", [
        f"✅ Tested {len(test_sentences)} sentences",
        f"✅ Compared {len(models_to_compare)} models",
    ])


if __name__ == "__main__":
    main()
