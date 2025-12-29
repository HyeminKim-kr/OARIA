"""
Demo: Watch Retry Handler in Action

This shows step-by-step how the retry logic works with simulated API errors.
"""

import asyncio
import random
from datetime import datetime

# Simulated error scenarios
class SimulatedAPI:
    """Simulates an API that sometimes fails."""

    def __init__(self):
        self.call_count = 0
        self.scenario = "rate_limit"  # rate_limit, timeout, success

    async def fetch(self, fail_times: int = 3):
        """
        Simulates API call that fails N times before succeeding.
        """
        self.call_count += 1

        if self.call_count <= fail_times:
            if self.scenario == "rate_limit":
                raise Exception("429 Rate Limited")
            elif self.scenario == "timeout":
                raise Exception("Timeout")

        return {"status": "success", "data": "Paper data here"}


def calculate_backoff(attempt: int, base: float = 1.0) -> float:
    """Calculate exponential backoff: 1s → 2s → 4s → 8s"""
    delay = base * (2 ** attempt)
    jitter = random.uniform(0, 0.5)
    return delay + jitter


async def demo_rate_limit():
    """Demo: Rate limit handling with exponential backoff."""

    print("\n" + "=" * 60)
    print("🔄 DEMO: Rate Limit (429) Handling")
    print("=" * 60)
    print("\nScenario: API returns 429 for first 3 calls, then succeeds.\n")

    api = SimulatedAPI()
    api.scenario = "rate_limit"

    max_retries = 5
    attempt = 0

    while attempt < max_retries:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Attempt {attempt + 1}/{max_retries}...")

        try:
            result = await api.fetch(fail_times=3)
            print(f"[{timestamp}] ✅ SUCCESS! Got: {result['status']}")
            print(f"\n📊 Total API calls: {api.call_count}")
            return result

        except Exception as e:
            print(f"[{timestamp}] ❌ FAILED: {e}")

            delay = calculate_backoff(attempt)
            print(f"[{timestamp}] ⏳ Waiting {delay:.1f}s (exponential backoff)...")
            print(f"             Formula: {1} × 2^{attempt} = {1 * (2**attempt)}s + jitter")

            # Actually wait (shortened for demo)
            await asyncio.sleep(min(delay, 2))  # Cap at 2s for demo

            attempt += 1
            print()

    print("❌ Max retries exceeded!")


async def demo_statistics():
    """Demo: Statistics collection."""

    print("\n" + "=" * 60)
    print("📊 DEMO: Statistics Collection")
    print("=" * 60)

    # Simulate a crawl session
    stats = {
        "total_requests": 0,
        "successful": 0,
        "retried": 0,
        "rate_limited": 0,
        "timeouts": 0,
        "failed": 0,
    }

    print("\nSimulating 20 API requests...\n")

    for i in range(20):
        stats["total_requests"] += 1

        # Simulate random outcomes
        outcome = random.choices(
            ["success", "success_retry", "rate_limit", "timeout"],
            weights=[70, 15, 10, 5]  # 70% success, 15% retry then success, etc.
        )[0]

        if outcome == "success":
            stats["successful"] += 1
            symbol = "✅"
        elif outcome == "success_retry":
            stats["successful"] += 1
            stats["retried"] += 1
            symbol = "🔄✅"
        elif outcome == "rate_limit":
            stats["rate_limited"] += 1
            stats["retried"] += 1
            stats["successful"] += 1  # Eventually succeeded
            symbol = "⚠️✅"
        else:
            stats["timeouts"] += 1
            stats["failed"] += 1
            symbol = "❌"

        print(f"  Request {i+1:2d}: {symbol}")
        await asyncio.sleep(0.1)

    # Print summary
    print("\n" + "-" * 40)
    print("📈 SESSION SUMMARY")
    print("-" * 40)

    success_rate = stats["successful"] / stats["total_requests"] * 100
    retry_rate = stats["retried"] / stats["total_requests"] * 100

    print(f"  Total Requests:    {stats['total_requests']}")
    print(f"  Successful:        {stats['successful']} ({success_rate:.1f}%)")
    print(f"  Retried:           {stats['retried']} ({retry_rate:.1f}%)")
    print(f"  Rate Limited:      {stats['rate_limited']}")
    print(f"  Timeouts:          {stats['timeouts']}")
    print(f"  Failed:            {stats['failed']}")


async def demo_backoff_visual():
    """Demo: Visualize exponential backoff."""

    print("\n" + "=" * 60)
    print("📈 DEMO: Exponential Backoff Visualization")
    print("=" * 60)

    print("\nFormula: delay = base × 2^attempt")
    print("With base = 1 second:\n")

    for attempt in range(6):
        delay = 1 * (2 ** attempt)
        bar = "█" * delay
        print(f"  Attempt {attempt}: {delay:2d}s {bar}")

    print("\n💡 This quickly reduces server load!")
    print("   After 5 failures, we've waited 1+2+4+8+16 = 31 seconds total")


async def main():
    """Run all demos."""

    print("\n" + "🚀" * 20)
    print("  OAR-22: RETRY HANDLER DEMO")
    print("🚀" * 20)

    # Demo 1: Backoff visualization
    await demo_backoff_visual()

    input("\n[Press Enter to continue to Rate Limit demo...]")

    # Demo 2: Rate limit handling
    await demo_rate_limit()

    input("\n[Press Enter to continue to Statistics demo...]")

    # Demo 3: Statistics
    await demo_statistics()

    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETE!")
    print("=" * 60)
    print("\nThis is what happens during a real crawl session.")
    print("The retry handler automatically handles all these scenarios.\n")


if __name__ == "__main__":
    asyncio.run(main())
