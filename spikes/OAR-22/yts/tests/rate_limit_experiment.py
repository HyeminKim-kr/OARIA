"""
Europe PMC API Rate Limit 실험

목표:
1. 어느 속도에서 429가 발생하는지 파악
2. Retry-After 헤더가 있는지 확인
3. 안전한 요청 간격 결정

주의:
- 실제 밴을 피하기 위해 점진적으로 테스트
- 429 발생 시 즉시 중단하고 대기
"""

import time
import httpx
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExperimentResult:
    """실험 결과"""
    delay: float              # 요청 간격 (초)
    total_requests: int       # 총 요청 수
    success_count: int        # 성공 수
    rate_limit_count: int     # 429 발생 수
    other_errors: int         # 기타 에러 수
    retry_after_values: list  # Retry-After 헤더 값들
    duration: float           # 총 소요 시간


def run_experiment(
    delay: float,
    num_requests: int = 20,
    timeout: float = 30.0,
) -> ExperimentResult:
    """특정 delay로 요청 실험"""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    # 가벼운 검색 쿼리 사용 (fulltext가 아닌 메타데이터만)
    SEARCH_URL = f"{BASE_URL}/search"

    results = {
        "success": 0,
        "rate_limit": 0,
        "other_error": 0,
        "retry_after": [],
    }

    print(f"\n{'='*50}")
    print(f"실험: delay={delay}s, requests={num_requests}")
    print(f"{'='*50}")

    start_time = time.time()

    with httpx.Client(timeout=timeout) as client:
        for i in range(num_requests):
            try:
                # 간단한 검색 쿼리 (가벼움)
                response = client.get(
                    SEARCH_URL,
                    params={
                        "query": "cancer",
                        "format": "json",
                        "pageSize": 1,
                    }
                )

                status = response.status_code

                if status == 200:
                    results["success"] += 1
                    print(f"  [{i+1:3d}] 200 OK")

                elif status == 429:
                    results["rate_limit"] += 1
                    retry_after = response.headers.get("Retry-After", "없음")
                    results["retry_after"].append(retry_after)
                    print(f"  [{i+1:3d}] 429 RATE LIMITED! Retry-After: {retry_after}")

                    # 429 발생 시 즉시 중단
                    print(f"\n  ⚠️ Rate Limit 발생! 실험 중단")
                    break

                else:
                    results["other_error"] += 1
                    print(f"  [{i+1:3d}] {status} {response.reason_phrase}")

            except httpx.TimeoutException:
                results["other_error"] += 1
                print(f"  [{i+1:3d}] TIMEOUT")

            except Exception as e:
                results["other_error"] += 1
                print(f"  [{i+1:3d}] ERROR: {e}")

            # 다음 요청 전 대기
            if i < num_requests - 1:
                time.sleep(delay)

    duration = time.time() - start_time
    total = results["success"] + results["rate_limit"] + results["other_error"]

    return ExperimentResult(
        delay=delay,
        total_requests=total,
        success_count=results["success"],
        rate_limit_count=results["rate_limit"],
        other_errors=results["other_error"],
        retry_after_values=results["retry_after"],
        duration=duration,
    )


def print_summary(results: list[ExperimentResult]):
    """실험 결과 요약 출력"""

    print(f"\n{'='*60}")
    print("실험 결과 요약")
    print(f"{'='*60}")
    print(f"{'Delay':>8} | {'Requests':>8} | {'Success':>8} | {'429':>5} | {'RPS':>6}")
    print(f"{'-'*60}")

    for r in results:
        rps = r.total_requests / r.duration if r.duration > 0 else 0
        print(f"{r.delay:>7.2f}s | {r.total_requests:>8} | {r.success_count:>8} | {r.rate_limit_count:>5} | {rps:>5.2f}")

    print(f"\n결론:")
    safe_delays = [r.delay for r in results if r.rate_limit_count == 0]
    if safe_delays:
        print(f"  - 안전한 최소 delay: {min(safe_delays):.2f}s")
    else:
        print(f"  - 모든 테스트에서 rate limit 발생!")


def main():
    """메인 실험 실행"""

    print(f"\n🔬 Europe PMC API Rate Limit 실험")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    # 실험 1: 보수적인 속도부터 시작 (안전)
    test_delays = [
        1.0,    # 1초 간격 (안전)
        0.5,    # 0.5초 간격
        0.3,    # 0.3초 간격 (현재 설정)
        0.2,    # 0.2초 간격
        0.1,    # 0.1초 간격 (위험)
    ]

    for delay in test_delays:
        result = run_experiment(delay=delay, num_requests=10)
        results.append(result)

        # 429 발생 시 더 빠른 테스트 중단
        if result.rate_limit_count > 0:
            print(f"\n⚠️ {delay}s에서 rate limit 발생. 더 빠른 테스트 중단")
            break

        # 다음 실험 전 안전 대기
        print(f"\n다음 실험 전 5초 대기...")
        time.sleep(5)

    print_summary(results)

    # Retry-After 분석
    all_retry_after = []
    for r in results:
        all_retry_after.extend(r.retry_after_values)

    if all_retry_after:
        print(f"\nRetry-After 헤더 값들: {all_retry_after}")
    else:
        print(f"\nRetry-After 헤더: 발생하지 않음 (429 없었음)")


if __name__ == "__main__":
    main()
