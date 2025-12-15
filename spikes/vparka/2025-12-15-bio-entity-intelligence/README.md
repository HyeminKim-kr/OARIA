# 🧬 Bio-Entity NER Fine-tuning

PubMedBERT 기반 바이오 개체명 인식(NER) 모델 학습 스크립트

## 📋 Requirements

```bash
pip install -r requirements.txt
```

> ⚠️ **중요**: `datasets==2.18.0` 버전 필수 (BC5CDR 데이터셋 호환성)

## 🚀 Quick Start

### 1. BC5CDR 단일 모델 (Chemical + Disease)

```bash
# 전체 학습 (Epoch 3, ~45분)
python train_pubmedbert_bc5cdr_ner.py

# 빠른 테스트 (~1분)
FAST_DEBUG=1 python train_pubmedbert_bc5cdr_ner.py
```

**데이터셋**: `tner/bc5cdr`  
**레이블**: `O`, `B-Chemical`, `I-Chemical`, `B-Disease`, `I-Disease`

---

### 2. Multi-NER 모델 (Chemical + Disease + Gene)

```bash
# 전체 학습 (Epoch 3, ~60분)
python train_pubmedbert_multiner.py

# 빠른 테스트 (~1분)
FAST_DEBUG=1 python train_pubmedbert_multiner.py
```

**데이터셋**:
| 데이터셋 | 개체 타입 | 원본 레이블 → 통합 레이블 |
|---------|---------|------------------------|
| `tner/bc5cdr` | Chemical, Disease | 그대로 유지 |
| `ncbi_disease` | Disease | 그대로 유지 |
| `jnlpba` | Gene/Protein | DNA, RNA, protein → Gene |

**레이블**: `O`, `B-Disease`, `I-Disease`, `B-Chemical`, `I-Chemical`, `B-Gene`, `I-Gene`

---

## ⚙️ Environment Variables

`.env.example`을 `.env`로 복사 후 설정:

```bash
cp .env.example .env
```

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `FAST_DEBUG` | `0` | `1`로 설정 시 빠른 디버그 모드 |
| `OUTPUT_DIR` | `./cancer-ner-pubmedbert` | 체크포인트 저장 경로 |
| `HF_HUB_MODEL_ID` | `vparka/cancer-ner-pubmedbert` | HuggingFace Hub 모델 ID |
| `HF_HUB_PRIVATE` | `true` | Hub 저장소 비공개 여부 |
| `SEED` | `42` | 랜덤 시드 |

---

## 🔧 FAST_DEBUG 모드

| 항목 | 일반 모드 | FAST_DEBUG |
|------|----------|------------|
| Epochs | 3 | 1 |
| Batch Size | 8 | 4 |
| Learning Rate | 2e-5 | 5e-5 |
| 데이터셋 크기 | 전체 | 100 샘플 |
| 평가 | 매 epoch | 건너뜀 |
| Hub Push | ✅ | ❌ |

---

## 📦 출력

학습 완료 후:
- `./OUTPUT_DIR/` - 체크포인트, config, tokenizer
- HuggingFace Hub에 자동 업로드 (FAST_DEBUG=0일 때)

---

## 🧪 추론 테스트

```python
from transformers import pipeline

ner = pipeline("ner", model="vparka/cancer-ner-pubmedbert", aggregation_strategy="simple")

text = "EGFR mutation is common in lung cancer treated with cisplatin."
for r in ner(text):
    print(f"- {r['word']} → {r['entity_group']} ({r['score']:.3f})")
```

---

## 📁 파일 구조

```
.
├── train_pubmedbert_bc5cdr_ner.py   # BC5CDR 단일 모델 학습
├── train_pubmedbert_multiner.py     # Multi-domain NER 학습
├── requirements.txt
├── .env.example
└── README.md
```
