"""
Europe PMC API Rate Limit 실험 v3 - 진짜 공격적인 테스트

목표: 1분 내에 429 발생 지점 파악
"""

import time
import httpx
from datetime import datetime


def aggressive_search_test():
    """Search API 무대기 연속 요청 - 429 나올 때까지"""
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    print(f"\n🔥 Search API 무대기 스트레스 테스트 (최대 100회)")
    print(f"{'='*50}")

    success = 0
    start = time.time()

    with httpx.Client(timeout=10) as client:
        for i in range(100):
            try:
                response = client.get(BASE_URL, params={"query": "cancer", "format": "json", "pageSize": 1})

                if response.status_code == 200:
                    success += 1
                elif response.status_code == 429:
                    elapsed = time.time() - start
                    retry_after = response.headers.get("Retry-After", "없음")
                    print(f"\n🚨 429 발생! {i+1}번째 요청에서")
                    print(f"   경과 시간: {elapsed:.1f}초")
                    print(f"   RPS: {(i+1)/elapsed:.2f}")
                    print(f"   Retry-After: {retry_after}")
                    return
                else:
                    print(f"  [{i+1}] {response.status_code}")

            except Exception as e:
                print(f"  [{i+1}] ERROR: {e}")

    elapsed = time.time() - start
    print(f"\n✅ 100회 완료, 429 없음!")
    print(f"   경과 시간: {elapsed:.1f}초")
    print(f"   RPS: {100/elapsed:.2f}")


def aggressive_fulltext_test():
    """Fulltext XML API 무대기 연속 요청"""
    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    # 존재하는 PMC ID들
    PMCIDS = ["PMC7096724", "PMC6955507", "PMC7153587", "PMC6834525", "PMC6755597",
              "PMC7147700", "PMC6958699", "PMC7140130", "PMC7086086", "PMC6955508"]

    print(f"\n🔥 Fulltext XML API 무대기 테스트 (10회)")
    print(f"{'='*50}")

    success = 0
    total_size = 0
    start = time.time()

    with httpx.Client(timeout=30) as client:
        for i, pmcid in enumerate(PMCIDS):
            try:
                response = client.get(f"{BASE_URL}/{pmcid}/fullTextXML")

                if response.status_code == 200:
                    success += 1
                    size_kb = len(response.content) / 1024
                    total_size += size_kb
                    print(f"  [{i+1}] OK ({size_kb:.0f} KB)")
                elif response.status_code == 429:
                    elapsed = time.time() - start
                    print(f"\n🚨 429 발생! {i+1}번째 요청에서")
                    print(f"   Retry-After: {response.headers.get('Retry-After', '없음')}")
                    return
                else:
                    print(f"  [{i+1}] {response.status_code}")

            except Exception as e:
                print(f"  [{i+1}] ERROR: {e}")

    elapsed = time.time() - start
    print(f"\n✅ {success}회 완료, 429 없음!")
    print(f"   경과 시간: {elapsed:.1f}초")
    print(f"   평균 다운로드: {total_size/success:.0f} KB/요청")
    print(f"   RPS: {success/elapsed:.2f}")


def main():
    print(f"🔬 Europe PMC Rate Limit v3 - 공격적 테스트")
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")

    aggressive_search_test()

    print(f"\n3초 대기 후 Fulltext 테스트...")
    time.sleep(3)

    aggressive_fulltext_test()

    print(f"\n완료: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
