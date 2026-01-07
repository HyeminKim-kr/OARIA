"""
Retry Handler for OARIA Paper Crawler (F-02)

Author: Hyemin Kim (AI Lead)
Task: OAR-101

Handles API rate limits and network errors with:
- Exponential backoff (1s → 2s → 4s → 8s → 16s)
- Configurable max retries
- Statistics collection
"""

# === IMPORTS ===

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

import httpx
import structlog

# Setup logger
logger = structlog.get_logger()

# Type variable for generic return type
T = TypeVar("T")


# === EXCEPTIONS ===

class RetryError(Exception):
    """Base exception for retry-related errors."""
    pass


class MaxRetriesExceeded(RetryError):
    """Raised when max retry attempts exceeded."""
    pass


# === STATISTICS ===

@dataclass
class RetryStats:
    """
    Collects statistics about retry operations.

    Useful for:
    - Monitoring API health
    - Detecting rate limit issues
    - Debugging network problems
    """
    total_requests: int = 0
    successful: int = 0
    retried: int = 0
    failed: int = 0
    rate_limited: int = 0
    timeouts: int = 0
    server_errors: int = 0

    def summary(self) -> dict:
        """Return summary statistics."""
        total = max(self.total_requests, 1)  # Avoid division by zero
        return {
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": round(self.successful / total * 100, 2),
            "retry_rate": round(self.retried / total * 100, 2),
            "rate_limited_count": self.rate_limited,
            "timeout_count": self.timeouts,
            "server_error_count": self.server_errors,
        }

    def reset(self):
        """Reset all counters."""
        self.total_requests = 0
        self.successful = 0
        self.retried = 0
        self.failed = 0
        self.rate_limited = 0
        self.timeouts = 0
        self.server_errors = 0


# === RETRY HANDLER ===

class RetryHandler:
    """
    Handles retry logic with exponential backoff.

    EXPONENTIAL BACKOFF EXPLAINED:
    ─────────────────────────────
    When an API returns 429 (rate limited), we don't retry immediately.
    Instead, we wait progressively longer:

        Attempt 0: Wait 1s
        Attempt 1: Wait 2s
        Attempt 2: Wait 4s
        Attempt 3: Wait 8s
        Attempt 4: Wait 16s

    This quickly reduces load on the server and increases success chance.

    JITTER:
    ───────
    We add random 0-1s to prevent "thundering herd" - when many clients
    retry at exactly the same time after a rate limit.

    Usage:
        handler = RetryHandler(max_retries=5)

        # Method 1: Execute async function
        response = await handler.execute(
            client.get,
            "https://api.example.com/data",
            params={"page": 1}
        )

        # Method 2: Use as decorator
        @handler.retry
        async def fetch_data():
            return await client.get(url)
    """

    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout_retries: int = 3,
        add_jitter: bool = True,
    ):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum retry attempts for rate limits/server errors
            base_delay: Base delay in seconds (default 1s)
            max_delay: Maximum delay cap in seconds (default 60s)
            timeout_retries: Max retries specifically for timeouts
            add_jitter: Add random 0-1s to prevent thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout_retries = timeout_retries
        self.add_jitter = add_jitter
        self.stats = RetryStats()

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.

        Formula: delay = base * 2^attempt + jitter

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential: 1, 2, 4, 8, 16, 32...
        delay = self.base_delay * (2 ** attempt)

        # Add jitter (0-1 second) to prevent thundering herd
        if self.add_jitter:
            jitter = random.uniform(0, 1)
            delay += jitter

        # Cap at max_delay
        return min(delay, self.max_delay)

    def _is_retryable(self, status_code: int) -> bool:
        """Check if HTTP status code is retryable."""
        return status_code in self.RETRYABLE_STATUS_CODES

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            MaxRetriesExceeded: If max retries exceeded
            httpx.HTTPStatusError: For non-retryable HTTP errors
        """
        attempt = 0
        timeout_attempts = 0
        last_exception: Optional[Exception] = None

        while True:
            try:
                self.stats.total_requests += 1
                result = await func(*args, **kwargs)

                # If httpx Response, check for HTTP errors
                if isinstance(result, httpx.Response):
                    result.raise_for_status()

                self.stats.successful += 1
                return result

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                last_exception = e

                if status_code == 429:
                    # Rate limited
                    self.stats.rate_limited += 1

                    if attempt >= self.max_retries:
                        self.stats.failed += 1
                        raise MaxRetriesExceeded(
                            f"Rate limited after {attempt + 1} attempts"
                        ) from e

                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        "rate_limited",
                        attempt=attempt + 1,
                        max_attempts=self.max_retries,
                        delay_seconds=round(delay, 2),
                    )

                    self.stats.retried += 1
                    await asyncio.sleep(delay)
                    attempt += 1

                elif status_code >= 500:
                    # Server error
                    self.stats.server_errors += 1

                    if attempt >= self.max_retries:
                        self.stats.failed += 1
                        raise MaxRetriesExceeded(
                            f"Server error {status_code} after {attempt + 1} attempts"
                        ) from e

                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        "server_error",
                        status_code=status_code,
                        attempt=attempt + 1,
                        delay_seconds=round(delay, 2),
                    )

                    self.stats.retried += 1
                    await asyncio.sleep(delay)
                    attempt += 1

                else:
                    # Non-retryable error (4xx except 429)
                    self.stats.failed += 1
                    logger.error(
                        "http_error",
                        status_code=status_code,
                        retryable=False,
                    )
                    raise

            except httpx.TimeoutException as e:
                # Timeout
                self.stats.timeouts += 1
                last_exception = e

                if timeout_attempts >= self.timeout_retries:
                    self.stats.failed += 1
                    raise MaxRetriesExceeded(
                        f"Timeout after {timeout_attempts + 1} attempts"
                    ) from e

                logger.warning(
                    "timeout",
                    attempt=timeout_attempts + 1,
                    max_attempts=self.timeout_retries,
                )

                self.stats.retried += 1
                await asyncio.sleep(5)  # Fixed 5s delay for timeouts
                timeout_attempts += 1

            except httpx.ConnectError as e:
                # Connection error
                last_exception = e

                if attempt >= self.max_retries:
                    self.stats.failed += 1
                    raise MaxRetriesExceeded(
                        f"Connection error after {attempt + 1} attempts"
                    ) from e

                delay = self._calculate_backoff(attempt)
                logger.warning(
                    "connection_error",
                    attempt=attempt + 1,
                    delay_seconds=round(delay, 2),
                )

                self.stats.retried += 1
                await asyncio.sleep(delay)
                attempt += 1


# === EXAMPLE USAGE ===

async def main():
    """
    Example: Test retry handler with simulated errors.

    Run with: python retry_handler.py
    """
    print("Testing Retry Handler")
    print("-" * 50)

    handler = RetryHandler(
        max_retries=5,
        base_delay=1.0,
        timeout_retries=3,
    )

    # Simulate backoff delays
    print("\nExponential Backoff Delays:")
    for attempt in range(5):
        delay = handler._calculate_backoff(attempt)
        print(f"  Attempt {attempt}: {delay:.2f}s")

    # Test statistics
    print("\nSimulating requests...")
    handler.stats.total_requests = 100
    handler.stats.successful = 95
    handler.stats.retried = 10
    handler.stats.failed = 5
    handler.stats.rate_limited = 8
    handler.stats.timeouts = 2

    print("\nStatistics Summary:")
    summary = handler.stats.summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("-" * 50)
    print("Retry handler test completed!")


if __name__ == "__main__":
    asyncio.run(main())
