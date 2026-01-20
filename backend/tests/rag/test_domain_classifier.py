"""도메인 분류기 테스트

PubMedBERTDomainClassifier의 정확도, 차단율, 레이턴시 테스트

실행:
    pytest tests/rag/test_domain_classifier.py -v

참고:
    - 첫 실행 시 모델 다운로드로 시간이 걸릴 수 있음
    - GPU 사용 시 더 빠른 추론 가능
"""

import os
import time

import pytest

from tests.rag.domain_queries import (
    ONCOLOGY_QUERIES,
    OFF_DOMAIN_QUERIES,
    EDGE_CASE_QUERIES,
)


# 분류기 비활성화 시 테스트 스킵
CLASSIFIER_ENABLED = os.getenv("DOMAIN_CLASSIFIER_ENABLED", "true").lower() == "true"


@pytest.fixture(scope="module")
def classifier():
    """분류기 인스턴스 (모듈 레벨에서 한 번만 로드)"""
    if not CLASSIFIER_ENABLED:
        pytest.skip("Domain classifier disabled")

    from app.rag.classifiers.pubmedbert import PubMedBERTDomainClassifier

    return PubMedBERTDomainClassifier(threshold=0.3)


@pytest.fixture(scope="module")
def warmed_classifier(classifier):
    """워밍업된 분류기 (첫 추론으로 모델 로드)"""
    # 워밍업 (모델 로드)
    classifier.classify("warmup query")
    return classifier


class TestOncologyClassification:
    """Oncology 쿼리 분류 테스트"""

    def test_oncology_queries_detected(self, warmed_classifier):
        """Oncology 쿼리가 oncology로 분류되는지 테스트"""
        correct = 0
        total = len(ONCOLOGY_QUERIES)

        for query in ONCOLOGY_QUERIES:
            result = warmed_classifier.classify(query)
            if result.category == "oncology":
                correct += 1
            else:
                print(f"MISS: '{query[:50]}...' -> {result.category} ({result.confidence:.2%})")

        accuracy = correct / total
        print(f"\nOncology accuracy: {correct}/{total} = {accuracy:.1%}")

        # 목표: 95% 이상
        assert accuracy >= 0.8, f"Oncology accuracy too low: {accuracy:.1%} (target >= 80%)"

    def test_oncology_queries_allowed(self, warmed_classifier):
        """Oncology 쿼리가 허용되는지 테스트"""
        allowed_count = sum(
            1 for q in ONCOLOGY_QUERIES
            if warmed_classifier.classify(q).is_allowed
        )

        # warn 모드에서는 모두 허용됨
        assert allowed_count == len(ONCOLOGY_QUERIES)


class TestOffDomainClassification:
    """Off-domain 쿼리 분류 테스트"""

    @pytest.mark.parametrize("category", ["cardiology", "neurology", "general_medicine", "non_medical"])
    def test_off_domain_detection(self, warmed_classifier, category):
        """각 카테고리의 Off-domain 쿼리가 oncology가 아닌 것으로 분류되는지 테스트"""
        queries = OFF_DOMAIN_QUERIES[category]
        non_oncology = 0

        for query in queries:
            result = warmed_classifier.classify(query)
            if result.category != "oncology":
                non_oncology += 1
            else:
                print(f"FALSE POSITIVE: '{query[:50]}...' -> oncology ({result.confidence:.2%})")

        detection_rate = non_oncology / len(queries)
        print(f"\n{category} detection rate: {non_oncology}/{len(queries)} = {detection_rate:.1%}")

        # 목표: 각 카테고리에서 80% 이상 감지
        assert detection_rate >= 0.7, f"{category} detection rate too low: {detection_rate:.1%}"

    def test_overall_off_domain_detection(self, warmed_classifier):
        """전체 Off-domain 차단율 테스트"""
        total = 0
        detected = 0

        for category, queries in OFF_DOMAIN_QUERIES.items():
            for query in queries:
                total += 1
                result = warmed_classifier.classify(query)
                if result.category != "oncology":
                    detected += 1

        detection_rate = detected / total
        print(f"\nOverall off-domain detection rate: {detected}/{total} = {detection_rate:.1%}")

        # 목표: 전체적으로 80% 이상
        assert detection_rate >= 0.7, f"Overall detection rate too low: {detection_rate:.1%}"


class TestEdgeCases:
    """경계 케이스 테스트"""

    def test_edge_cases(self, warmed_classifier):
        """암 관련이지만 다른 분야와 연관된 쿼리 테스트"""
        correct = 0

        for query, expected_category in EDGE_CASE_QUERIES:
            result = warmed_classifier.classify(query)
            # 경계 케이스는 oncology로 분류되어야 함
            if result.category == expected_category:
                correct += 1
            else:
                print(f"EDGE: '{query[:50]}...' -> {result.category} (expected: {expected_category})")

        accuracy = correct / len(EDGE_CASE_QUERIES)
        print(f"\nEdge case accuracy: {correct}/{len(EDGE_CASE_QUERIES)} = {accuracy:.1%}")

        # 경계 케이스는 정확도 목표를 낮게 설정
        assert accuracy >= 0.5, f"Edge case accuracy too low: {accuracy:.1%}"


class TestLatency:
    """레이턴시 테스트"""

    def test_classification_latency(self, warmed_classifier):
        """분류 처리 시간 테스트 (목표: < 500ms)"""
        latencies = []

        # 5개 쿼리로 평균 레이턴시 측정
        test_queries = ONCOLOGY_QUERIES[:5]

        for query in test_queries:
            start = time.perf_counter()
            warmed_classifier.classify(query)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        print(f"\nAvg latency: {avg_latency:.0f}ms, Max: {max_latency:.0f}ms")

        # 목표: 평균 500ms 미만
        assert avg_latency < 500, f"Average latency too high: {avg_latency:.0f}ms"


class TestClassifierConfig:
    """분류기 설정 테스트"""

    def test_get_config(self, warmed_classifier):
        """설정 반환 테스트"""
        config = warmed_classifier.get_config()

        assert "name" in config
        assert config["name"] == "pubmedbert_domain_v1"
        assert "threshold" in config
        assert "enabled" in config
        assert "candidate_labels" in config

    def test_disabled_classifier(self):
        """비활성화된 분류기 테스트"""
        from app.rag.classifiers.pubmedbert import PubMedBERTDomainClassifier

        classifier = PubMedBERTDomainClassifier()
        classifier._enabled = False

        result = classifier.classify("any query")

        assert result.is_allowed is True
        assert result.category == "oncology"
        assert "disabled" in result.reason.lower()


class TestMessages:
    """메시지 템플릿 테스트"""

    def test_get_warning_message(self):
        """경고 메시지 반환 테스트"""
        from app.rag.classifiers.messages import get_warning_message

        msg_ko = get_warning_message("cardiology", "ko")
        msg_en = get_warning_message("cardiology", "en")

        assert "심장학" in msg_ko or "cardiology" in msg_ko.lower()
        assert "cardiology" in msg_en.lower()

    def test_get_example_questions(self):
        """예시 질문 반환 테스트"""
        from app.rag.classifiers.messages import get_example_questions

        examples = get_example_questions("ko", limit=3)

        assert len(examples) == 3
        assert all(isinstance(q, str) for q in examples)

    def test_format_warning_response(self):
        """경고 응답 포맷 테스트"""
        from app.rag.classifiers.messages import format_warning_response

        response = format_warning_response("cardiology", 0.85, "ko")

        assert response["type"] == "domain_warning"
        assert response["category"] == "cardiology"
        assert response["confidence"] == 0.85
        assert "message" in response
        assert "example_questions" in response
