"""도메인 분류 경고/거절 메시지 템플릿

Off-domain 쿼리 감지 시 사용자에게 안내할 메시지를 제공합니다.
다국어 지원 (한국어, 영어)
"""

from typing import Literal

Language = Literal["ko", "en"]


# 도메인별 경고 메시지
DOMAIN_WARNING_MESSAGES = {
    "cardiology": {
        "ko": (
            "이 질문은 심장학(cardiology) 분야로 분류되었습니다. "
            "OARIA는 종양학(암 연구) 전문 AI로, 심장학 관련 답변의 정확도가 낮을 수 있습니다."
        ),
        "en": (
            "This query has been classified as cardiology-related. "
            "OARIA specializes in oncology (cancer research), so answers about cardiology may be less accurate."
        ),
    },
    "neurology": {
        "ko": (
            "이 질문은 신경학(neurology) 분야로 분류되었습니다. "
            "OARIA는 종양학(암 연구) 전문 AI로, 신경학 관련 답변의 정확도가 낮을 수 있습니다."
        ),
        "en": (
            "This query has been classified as neurology-related. "
            "OARIA specializes in oncology (cancer research), so answers about neurology may be less accurate."
        ),
    },
    "general_medicine": {
        "ko": (
            "이 질문은 일반 의학 분야로 분류되었습니다. "
            "OARIA는 종양학(암 연구) 전문 AI로, 일반 의학 관련 답변의 정확도가 낮을 수 있습니다."
        ),
        "en": (
            "This query has been classified as general medicine. "
            "OARIA specializes in oncology (cancer research), so general medical answers may be less accurate."
        ),
    },
    "non_medical": {
        "ko": (
            "이 질문은 의학 외 분야로 분류되었습니다. "
            "OARIA는 종양학(암 연구) 논문 기반 AI입니다. 암 관련 질문을 해주세요."
        ),
        "en": (
            "This query has been classified as non-medical. "
            "OARIA is an oncology research AI. Please ask cancer-related questions."
        ),
    },
}

# 기본 경고 메시지 (분류 실패 시)
DEFAULT_WARNING_MESSAGE = {
    "ko": "질문 분류 중 오류가 발생했습니다. 답변의 정확도가 낮을 수 있습니다.",
    "en": "An error occurred during query classification. Answers may be less accurate.",
}

# Oncology 관련 예시 질문
EXAMPLE_ONCOLOGY_QUESTIONS = {
    "ko": [
        "EGFR 변이 비소세포폐암의 표적 치료제는 무엇인가요?",
        "면역관문억제제(pembrolizumab)의 작용 기전을 설명해주세요.",
        "HER2 양성 유방암의 최신 치료 가이드라인은?",
        "KRAS G12C 변이 폐암에 사용 가능한 약물은?",
        "CAR-T 세포 치료의 원리와 적응증은?",
    ],
    "en": [
        "What are targeted therapies for EGFR-mutant NSCLC?",
        "Explain the mechanism of action of pembrolizumab.",
        "What are the latest treatment guidelines for HER2+ breast cancer?",
        "What drugs are available for KRAS G12C mutant lung cancer?",
        "What are the principles and indications of CAR-T cell therapy?",
    ],
}

# 시스템 소개 메시지
SYSTEM_INTRO = {
    "ko": "OARIA는 종양학(암 연구) 논문을 기반으로 한 전문 AI 어시스턴트입니다.",
    "en": "OARIA is a specialized AI assistant based on oncology (cancer research) papers.",
}


def get_warning_message(category: str, language: Language = "ko") -> str:
    """도메인별 경고 메시지 반환

    Args:
        category: 분류된 도메인 카테고리
        language: 언어 코드 (ko/en)

    Returns:
        경고 메시지 문자열
    """
    messages = DOMAIN_WARNING_MESSAGES.get(category, DEFAULT_WARNING_MESSAGE)
    return messages.get(language, messages.get("en", ""))


def get_example_questions(language: Language = "ko", limit: int = 3) -> list[str]:
    """Oncology 예시 질문 반환

    Args:
        language: 언어 코드 (ko/en)
        limit: 반환할 예시 개수

    Returns:
        예시 질문 목록
    """
    questions = EXAMPLE_ONCOLOGY_QUESTIONS.get(language, EXAMPLE_ONCOLOGY_QUESTIONS["en"])
    return questions[:limit]


def format_warning_response(
    category: str,
    confidence: float,
    language: Language = "ko",
    include_examples: bool = True,
) -> dict:
    """SSE 경고 이벤트용 페이로드 생성

    Args:
        category: 분류된 도메인 카테고리
        confidence: 분류 신뢰도 (0~1)
        language: 언어 코드
        include_examples: 예시 질문 포함 여부

    Returns:
        경고 이벤트 페이로드 딕셔너리
    """
    response = {
        "type": "domain_warning",
        "category": category,
        "confidence": round(confidence, 3),
        "message": get_warning_message(category, language),
        "system_intro": SYSTEM_INTRO.get(language, SYSTEM_INTRO["en"]),
    }

    if include_examples:
        response["example_questions"] = get_example_questions(language, limit=3)

    return response


def get_full_warning_text(
    category: str,
    confidence: float,
    language: Language = "ko",
) -> str:
    """전체 경고 텍스트 생성 (예시 포함)

    Args:
        category: 분류된 도메인 카테고리
        confidence: 분류 신뢰도
        language: 언어 코드

    Returns:
        전체 경고 메시지 문자열
    """
    message = get_warning_message(category, language)
    examples = get_example_questions(language, limit=3)

    if language == "ko":
        text = f"{message}\n\n예시 질문:\n"
        text += "\n".join(f"  • {q}" for q in examples)
    else:
        text = f"{message}\n\nExample questions:\n"
        text += "\n".join(f"  • {q}" for q in examples)

    return text
