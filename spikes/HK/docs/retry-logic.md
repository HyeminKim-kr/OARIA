# Retry Logic Design

> **Task**: OAR-101 (sub-task of OAR-22)
>
> **Owner**: Hyemin Kim (AI Lead)
>
> **Version**: v1.0 (2025-12-28)

---

## ADR Compliance

This implementation follows ADR-007 from `CLAUDE.md`:

| ADR | Decision | Implementation |
|-----|----------|----------------|
| ADR-007 | Async-first | `async/await` pattern for HTTP calls and retry logic |

---

## Original Spec

### Requirements (OAR-22)

```
Rate Limit and Network Error Retry Logic:
- 429 error: Exponential backoff (1s → 2s → 4s → 8s)
- Network timeout: Max 3 retries
- Parsing failure: Log and skip
- Max retries: 5 times
- Collect failure statistics
```

---

## Why Retry Logic Matters

### The Problem

API calls can fail for various reasons:

1. **Rate limiting (429)** - Too many requests, need to slow down
2. **Network timeout** - Server too slow or network issues
3. **Connection errors** - Temporary network blips
4. **Server errors (5xx)** - Server overloaded or maintenance

### Without Retry

```
Request → 429 Error → Crash!
Lost all progress, must restart from beginning
```

### With Retry

```
Request → 429 Error → Wait 1s → Retry → Success!
Graceful handling, continues from where it left off
```

---

## Exponential Backoff Explained

### Why Exponential?

Linear backoff (1s, 2s, 3s, 4s) doesn't help when server is overloaded.
Exponential backoff (1s, 2s, 4s, 8s) quickly reduces load on server.

### Formula

```python
delay = base * (2 ** attempt)

# Example with base=1:
# Attempt 0: 1 * 2^0 = 1s
# Attempt 1: 1 * 2^1 = 2s
# Attempt 2: 1 * 2^2 = 4s
# Attempt 3: 1 * 2^3 = 8s
# Attempt 4: 1 * 2^4 = 16s
```

### With Jitter (Optional)

Add randomness to prevent "thundering herd" when multiple clients retry:

```python
delay = base * (2 ** attempt) + random.uniform(0, 1)
```

---

## Error Classification

### Retryable Errors

| Error | HTTP Code | Retry? | Strategy |
|-------|-----------|--------|----------|
| Rate Limited | 429 | Yes | Exponential backoff |
| Server Error | 500, 502, 503, 504 | Yes | Exponential backoff |
| Timeout | - | Yes | Fixed delay |
| Connection Error | - | Yes | Exponential backoff |

### Non-Retryable Errors

| Error | HTTP Code | Retry? | Action |
|-------|-----------|--------|--------|
| Bad Request | 400 | No | Log and skip |
| Unauthorized | 401 | No | Fail immediately |
| Not Found | 404 | No | Log and skip |
| Parse Error | - | No | Log and skip |

---

## Implementation Details

### RetryHandler Class

```python
class RetryHandler:
    """
    Handles retry logic with exponential backoff.

    Usage:
        handler = RetryHandler(max_retries=5)
        response = await handler.execute(
            func=client.get,
            args=(url,),
            kwargs={"params": params}
        )
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout_retries: int = 3,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout_retries = timeout_retries
        self.stats = RetryStats()
```

### Execute with Retry

```python
async def execute(self, func, *args, **kwargs):
    """Execute function with retry logic."""
    attempt = 0

    while attempt < self.max_retries:
        try:
            self.stats.total_requests += 1
            result = await func(*args, **kwargs)
            self.stats.successful += 1
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self.stats.rate_limited += 1
                delay = self._calculate_backoff(attempt)
                logger.warning("rate_limited", attempt=attempt, delay=delay)
                await asyncio.sleep(delay)
                attempt += 1

            elif e.response.status_code >= 500:
                delay = self._calculate_backoff(attempt)
                logger.warning("server_error", status=e.response.status_code)
                await asyncio.sleep(delay)
                attempt += 1

            else:
                # Non-retryable error (4xx except 429)
                self.stats.failed += 1
                raise

        except httpx.TimeoutException:
            self.stats.timeouts += 1
            if attempt < self.timeout_retries:
                logger.warning("timeout", attempt=attempt)
                await asyncio.sleep(5)  # Fixed delay for timeout
                attempt += 1
            else:
                self.stats.failed += 1
                raise

    # Max retries exceeded
    self.stats.failed += 1
    raise MaxRetriesExceeded(f"Failed after {self.max_retries} attempts")
```

### Backoff Calculator

```python
def _calculate_backoff(self, attempt: int) -> float:
    """Calculate exponential backoff delay."""
    delay = self.base_delay * (2 ** attempt)
    # Add jitter (0-1 second)
    jitter = random.uniform(0, 1)
    return min(delay + jitter, self.max_delay)
```

---

## Statistics Collection

### RetryStats Dataclass

```python
@dataclass
class RetryStats:
    total_requests: int = 0
    successful: int = 0
    retried: int = 0
    failed: int = 0
    rate_limited: int = 0
    timeouts: int = 0

    def summary(self) -> dict:
        return {
            "total": self.total_requests,
            "success_rate": self.successful / max(self.total_requests, 1),
            "retry_rate": self.retried / max(self.total_requests, 1),
            "rate_limit_count": self.rate_limited,
            "timeout_count": self.timeouts,
        }
```

---

## Integration with OpenAlex Client

### Before (OAR-94)

```python
# Simple 60s wait
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        await asyncio.sleep(60)
        continue
```

### After (OAR-101)

```python
# Use RetryHandler
self.retry_handler = RetryHandler(max_retries=5)

response = await self.retry_handler.execute(
    self._client.get,
    f"{self.BASE_URL}/works",
    params=params,
)
```

---

## Acceptance Criteria Status

| Criteria | Original | Implementation | Status |
|----------|----------|----------------|--------|
| 429 auto-wait | Exponential backoff | `_calculate_backoff()` | ✅ Designed |
| Max 5 retries | Same | `max_retries=5` | ✅ Designed |
| Failure statistics | Same | `RetryStats` dataclass | ✅ Designed |

---

## References

- [Exponential Backoff](https://en.wikipedia.org/wiki/Exponential_backoff)
- [OpenAlex Rate Limits](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication)
- [httpx Exceptions](https://www.python-httpx.org/exceptions/)
