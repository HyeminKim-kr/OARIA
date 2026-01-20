"""
Europe PMC API Rate Limit 실험 v2 - 더 공격적인 테스트

v1 결과: 0.1초 간격에서도 429 미발생 (search API)

v2 목표:
1. 더 빠른 속도 테스트 (0.05s, 0s)
2. fulltext XML 요청 테스트
3. 더 많은 요청 (50회)
"""

import time
import httpx
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExperimentResult:
    delay: float
    total_requests: int
    success_count: int
    rate_limit_count: int
    other_errors: int
    retry_after_values: list
    duration: float
    api_type: str


def run_search_experiment(delay: float, num_requests: int = 50) -> ExperimentResult:
    """Search API 테스트 (가벼움)"""
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    results = {"success": 0, "rate_limit": 0, "other_error": 0, "retry_after": []}
    start_time = time.time()

    print(f"\n[Search API] delay={delay}s, requests={num_requests}")

    with httpx.Client(timeout=30) as client:
        for i in range(num_requests):
            try:
                response = client.get(BASE_URL, params={"query": "cancer", "format": "json", "pageSize": 1})

                if response.status_code == 200:
                    results["success"] += 1
                    if (i + 1) % 10 == 0:
                        print(f"  [{i+1:3d}] OK")
                elif response.status_code == 429:
                    results["rate_limit"] += 1
                    retry_after = response.headers.get("Retry-After", "없음")
                    results["retry_after"].append(retry_after)
                    print(f"  [{i+1:3d}] 429! Retry-After: {retry_after}")
                    break
                else:
                    results["other_error"] += 1
                    print(f"  [{i+1:3d}] {response.status_code}")

            except Exception as e:
                results["other_error"] += 1
                print(f"  [{i+1:3d}] ERROR: {e}")

            if delay > 0 and i < num_requests - 1:
                time.sleep(delay)

    return ExperimentResult(
        delay=delay,
        total_requests=results["success"] + results["rate_limit"] + results["other_error"],
        success_count=results["success"],
        rate_limit_count=results["rate_limit"],
        other_errors=results["other_error"],
        retry_after_values=results["retry_after"],
        duration=time.time() - start_time,
        api_type="search",
    )


def run_fulltext_experiment(delay: float, num_requests: int = 20) -> ExperimentResult:
    """Fulltext XML API 테스트 (무거움)"""
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    # 실제 존재하는 PMC ID들 (테스트용)
    TEST_PMCIDS = [
        "PMC7096724", "PMC6955507", "PMC7153587", "PMC6834525", "PMC6755597",
        "PMC7147700", "PMC6958699", "PMC7140130", "PMC7086086", "PMC6955508",
        "PMC7094527", "PMC6955509", "PMC7137669", "PMC7133564", "PMC7108158",
        "PMC7140131", "PMC7147701", "PMC7096725", "PMC7153588", "PMC6834526",
    ]

    results = {"success": 0, "rate_limit": 0, "other_error": 0, "retry_after": []}
    start_time = time.time()

    print(f"\n[Fulltext XML API] delay={delay}s, requests={num_requests}")

    with httpx.Client(timeout=60) as client:
        for i in range(min(num_requests, len(TEST_PMCIDS))):
            pmcid = TEST_PMCIDS[i]
            url = f"{BASE_URL}/{pmcid}/fullTextXML"

            try:
                response = client.get(url)

                if response.status_code == 200:
                    results["success"] += 1
                    # XML 크기 확인
                    size_kb = len(response.content) / 1024
                    print(f"  [{i+1:3d}] OK ({size_kb:.1f} KB)")
                elif response.status_code == 429:
                    results["rate_limit"] += 1
                    retry_after = response.headers.get("Retry-After", "없음")
                    results["retry_after"].append(retry_after)
                    print(f"  [{i+1:3d}] 429! Retry-After: {retry_after}")
                    break
                elif response.status_code == 404:
                    results["other_error"] += 1
                    print(f"  [{i+1:3d}] 404 (not found)")
                else:
                    results["other_error"] += 1
                    print(f"  [{i+1:3d}] {response.status_code}")

            except Exception as e:
                results["other_error"] += 1
                print(f"  [{i+1:3d}] ERROR: {e}")

            if delay > 0 and i < num_requests - 1:
                time.sleep(delay)

    return ExperimentResult(
        delay=delay,
        total_requests=results["success"] + results["rate_limit"] + results["other_error"],
        success_count=results["success"],
        rate_limit_count=results["rate_limit"],
        other_errors=results["other_error"],
        retry_after_values=results["retry_after"],
        duration=time.time() - start_time,
        api_type="fulltext",
    )


def print_summary(results: list[ExperimentResult]):
    print(f"\n{'='*70}")
    print("실험 결과 요약")
    print(f"{'='*70}")
    print(f"{'API Type':>10} | {'Delay':>7} | {'Requests':>8} | {'Success':>7} | {'429':>5} | {'RPS':>6}")
    print(f"{'-'*70}")

    for r in results:
        rps = r.total_requests / r.duration if r.duration > 0 else 0
        print(f"{r.api_type:>10} | {r.delay:>6.2f}s | {r.total_requests:>8} | {r.success_count:>7} | {r.rate_limit_count:>5} | {rps:>5.2f}")


def main():
    print(f"\n🔬 Europe PMC API Rate Limit 실험 v2 (공격적)")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n⚠️ 주의: 이 테스트는 더 공격적입니다!")

    results = []

    # 실험 1: Search API - 더 빠른 속도
    print(f"\n{'='*70}")
    print("1단계: Search API 스트레스 테스트")
    print(f"{'='*70}")

    for delay in [0.05, 0.0]:  # 0.05초, 무대기
        result = run_search_experiment(delay=delay, num_requests=50)
        results.append(result)

        if result.rate_limit_count > 0:
            print(f"\n⚠️ {delay}s에서 rate limit 발생!")
            break

        print(f"대기 10초...")
        time.sleep(10)

    # 실험 2: Fulltext XML API
    print(f"\n{'='*70}")
    print("2단계: Fulltext XML API 테스트 (더 무거움)")
    print(f"{'='*70}")

    for delay in [0.3, 0.1, 0.0]:
        result = run_fulltext_experiment(delay=delay, num_requests=20)
        results.append(result)

        if result.rate_limit_count > 0:
            print(f"\n⚠️ Fulltext API에서 rate limit 발생!")
            break

        print(f"대기 10초...")
        time.sleep(10)

    print_summary(results)

    # 결론
    print(f"\n{'='*70}")
    print("결론 및 권장 설정")
    print(f"{'='*70}")

    search_safe = [r for r in results if r.api_type == "search" and r.rate_limit_count == 0]
    fulltext_safe = [r for r in results if r.api_type == "fulltext" and r.rate_limit_count == 0]

    if search_safe:
        min_delay = min(r.delay for r in search_safe)
        print(f"  Search API 안전 최소 delay: {min_delay}s")

    if fulltext_safe:
        min_delay = min(r.delay for r in fulltext_safe)
        print(f"  Fulltext API 안전 최소 delay: {min_delay}s")


if __name__ == "__main__":
    main()
