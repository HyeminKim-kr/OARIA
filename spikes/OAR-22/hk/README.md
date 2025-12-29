# OAR-22: Rate Limit Handling & Retry Logic

> **Owner**: hk (Hyemin Kim)
>
> **Sub-task**: OAR-101
>
> **Purpose**: Handle API rate limits and network errors with automatic retry

---

## Original Spec vs Current Implementation

### Original Requirement (OAR-22)

The original task specified:
- **429 error**: Exponential backoff (1s → 2s → 4s → 8s)
- **Network timeout**: Max 3 retries
- **Parsing failure**: Log and skip
- **Max retries**: 5 times
- **Statistics**: Collect failure counts

### Current State (OAR-94)

Basic rate limiting exists in `openalex_client.py`:

```python
# Current implementation (line 454-458)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        logger.warning("rate_limited", retry_after_seconds=60)
        await asyncio.sleep(60)  # Fixed 60s wait
        continue
```

**What's missing:**
- Exponential backoff (currently fixed 60s)
- Network timeout handling
- Retry count limit
- Failure statistics

---

## Implementation Status: ENHANCEMENT

This task enhances the existing OAR-94 implementation.

### Location

```
spikes/OAR-22/hk/src/retry_handler.py
└── RetryHandler class (reusable wrapper)

# Also updates:
spikes/OAR-18/hk/src/openalex_client.py
└── Integration with RetryHandler
```

### Retry Strategy

| Error Type | Strategy | Max Retries |
|------------|----------|-------------|
| 429 Rate Limit | Exponential backoff (1s → 2s → 4s → 8s → 16s) | 5 |
| Network Timeout | Fixed 5s wait | 3 |
| Connection Error | Exponential backoff | 3 |
| Parsing Error | Log and skip | 0 (no retry) |

---

## Retry Logic Breakdown

### Step 1: Exponential Backoff Calculator

```python
def calculate_backoff(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate delay: 1s → 2s → 4s → 8s → 16s (capped at max_delay)."""
    delay = base * (2 ** attempt)
    return min(delay, max_delay)
```

### Step 2: Retry Decorator

```python
@retry(
    max_attempts=5,
    retry_on=(httpx.HTTPStatusError, httpx.TimeoutException),
    backoff=exponential_backoff,
)
async def fetch_with_retry(url: str) -> Response:
    ...
```

### Step 3: Statistics Collection

```python
@dataclass
class RetryStats:
    total_requests: int = 0
    successful: int = 0
    retried: int = 0
    failed: int = 0
    rate_limited: int = 0
    timeouts: int = 0
```

---

## Folder Structure

```
OAR-22/hk/
├── README.md                    # This file
├── docs/
│   └── retry-logic.md           # Detailed design document
├── src/
│   └── retry_handler.py         # Retry logic implementation
└── output/                      # Test outputs
```

---

## Acceptance Criteria Status

| Criteria | Original | Status |
|----------|----------|--------|
| 429 auto-wait | Exponential backoff | Pending |
| Max 5 retries | Same | Pending |
| Failure statistics | Same | Pending |

---

## References

- [OAR-94 OpenAlex Client](../../OAR-18/hk/src/openalex_client.py) - Current rate limit handling
- [OpenAlex Rate Limits](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication)
- [httpx Timeout Docs](https://www.python-httpx.org/advanced/#timeout-configuration)
