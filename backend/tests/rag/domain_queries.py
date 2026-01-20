"""도메인 분류 테스트 데이터셋

Oncology vs Off-domain 쿼리 테스트용 데이터
"""

# Oncology (암 연구) 관련 쿼리 - 허용되어야 함
ONCOLOGY_QUERIES = [
    # EGFR / 폐암
    "EGFR 변이 비소세포폐암의 1차 치료 옵션은 무엇인가요?",
    "What is the mechanism of action of osimertinib in EGFR-mutant NSCLC?",
    "EGFR T790M 내성 돌연변이의 치료 전략",
    "Afatinib과 gefitinib의 효능 비교",
    # 면역항암제
    "Pembrolizumab의 작용 기전을 설명해주세요",
    "PD-1/PD-L1 면역관문억제제의 부작용은?",
    "Nivolumab과 ipilimumab 병용요법의 효과",
    "CAR-T 세포 치료의 원리와 적응증",
    # 유방암 / HER2
    "HER2 양성 유방암의 최신 치료 가이드라인",
    "Trastuzumab 내성 기전과 극복 방안",
    "Triple negative breast cancer의 표적 치료",
    # 대장암 / KRAS
    "KRAS G12C 변이 대장암 치료제",
    "Cetuximab 적응증과 RAS 변이 검사",
    # 혈액암
    "급성 골수성 백혈병(AML)의 표적 치료제",
    "만성 골수성 백혈병의 TKI 치료 가이드라인",
    "다발성 골수종의 최신 치료 옵션",
    # 기타 암종
    "췌장암의 FOLFIRINOX 요법",
    "간세포암에서 sorafenib의 역할",
    "신장암의 면역항암제 치료",
    "두경부암 방사선 치료와 화학요법 병용",
]

# Cardiology (심장학) 관련 쿼리 - 거절되어야 함
CARDIOLOGY_QUERIES = [
    "심근경색의 응급 치료 프로토콜은 무엇인가요?",
    "What are the latest guidelines for atrial fibrillation management?",
    "심방세동 환자의 항응고 치료 전략",
    "급성 심부전의 약물 치료",
    "관상동맥 우회술의 적응증",
    "심실빈맥의 ICD 적응증",
    "고혈압 약물 치료 1차 선택약",
]

# Neurology (신경학) 관련 쿼리 - 거절되어야 함
NEUROLOGY_QUERIES = [
    "파킨슨병의 도파민 치료 최적화 방법",
    "What is the pathophysiology of Alzheimer's disease?",
    "뇌졸중 급성기 혈전용해 치료",
    "다발성 경화증의 면역조절 치료",
    "간질 발작의 약물 치료 가이드라인",
    "편두통 예방 치료",
    "근위축성 측삭경화증(ALS)의 치료 옵션",
]

# General Medicine (일반 의학) 관련 쿼리 - 거절되어야 함
GENERAL_MEDICINE_QUERIES = [
    "제2형 당뇨병의 약물 치료 순서",
    "류마티스 관절염의 생물학적 제제",
    "천식 환자의 흡입제 사용법",
    "만성 신장병의 식이 요법",
    "갑상선 기능 저하증 호르몬 대체 요법",
]

# Non-medical (의학 외) 쿼리 - 거절되어야 함
NON_MEDICAL_QUERIES = [
    "오늘 서울 날씨가 어떤가요?",
    "파이썬으로 웹 서버 만드는 방법",
    "주식 투자 전략을 알려주세요",
    "맛있는 파스타 레시피",
    "영어 문법 공부 방법",
    "좋은 운동 루틴 추천해주세요",
]

# 모든 Off-domain 쿼리
OFF_DOMAIN_QUERIES = {
    "cardiology": CARDIOLOGY_QUERIES,
    "neurology": NEUROLOGY_QUERIES,
    "general_medicine": GENERAL_MEDICINE_QUERIES,
    "non_medical": NON_MEDICAL_QUERIES,
}

# 경계 케이스 (암 관련이지만 다른 분야와 연관)
EDGE_CASE_QUERIES = [
    # 암 + 심장 (암 치료의 심독성)
    ("anthracycline 심독성 예방 방법", "oncology"),  # 암 치료 부작용
    ("trastuzumab의 심장 모니터링", "oncology"),  # HER2 치료 부작용
    # 암 + 신경 (뇌종양, 전이)
    ("뇌전이 폐암의 치료 전략", "oncology"),  # 암 전이
    ("교모세포종의 표적 치료", "oncology"),  # 뇌종양
    # 암 + 일반 (암 환자 합병증)
    ("암 환자의 혈전증 예방", "oncology"),  # 암 합병증
    ("항암 치료 중 감염 관리", "oncology"),  # 암 지지요법
]
