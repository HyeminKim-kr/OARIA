2025-12-15-bio-entity-intelligence/
├── README.md
├── requirements.txt
├── .env.example
│
├── config/
│   ├── base.py              # 공통 설정
│   ├── train.py             # 학습 파라미터
│   └── hub.py               # Hugging Face Hub 설정
│
├── data/
│   └── loader.py            # dataset 로드
│
├── model/
│   ├── tokenizer.py
│   ├── model.py
│
├── training/
│   ├── metrics.py
│   ├── trainer.py
│   └── callbacks.py         # 로깅 / hook
│
├── inference/
│   └── test.py
│
├── utils/
│   ├── logger.py            # ⭐ 컬러 로깅 핵심
│   └── env.py
│
└── main.py                  # 🔥 실행 진입점
