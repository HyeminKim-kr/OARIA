# Batch Scheduler Design Document

## Overview

The batch scheduler automates paper collection from OpenAlex API with two modes:
1. **Initial Collection**: One-time backfill of historical papers
2. **Incremental Collection**: Daily collection of new papers

## Design Decisions

### ADR-001: Cursor-based Pagination

**Decision**: Use OpenAlex cursor pagination instead of offset-based.

**Rationale**:
- Cursor pagination is stable across concurrent modifications
- Better performance for large result sets
- Recommended by OpenAlex for >10,000 results

```python
# Cursor pagination
params = {
    "cursor": "*",  # Start cursor
    "per-page": 200
}

# Response contains next cursor
next_cursor = data["meta"]["next_cursor"]
```

### ADR-002: Batch Size of 200

**Decision**: Default batch size of 200 papers per request.

**Rationale**:
- OpenAlex max is 200 per request
- Balances throughput vs memory usage
- Reduces total API calls

### ADR-003: Date-based Incremental Filter

**Decision**: Use `from_publication_date` filter for incremental crawls.

**Rationale**:
- More reliable than `from_created_date`
- Catches newly published papers
- May include some duplicates (handled by deduplication)

```python
filter = "from_publication_date:2025-12-28"
```

## Collection Modes

### Initial Collection

```
┌──────────────────────────────────────────────────────┐
│                 Initial Collection                    │
├──────────────────────────────────────────────────────┤
│  1. Calculate start date (today - 5 years)           │
│  2. Build filter: concepts + has_abstract + date     │
│  3. Fetch batches with cursor pagination             │
│  4. Parse and deduplicate each batch                 │
│  5. Save to database                                 │
│  6. Log progress and statistics                      │
│  7. Continue until max_papers or no more results     │
└──────────────────────────────────────────────────────┘
```

**Estimated time**: ~4 hours for 50,000 papers (at 200/batch, 0.1s delay)

### Incremental Collection

```
┌──────────────────────────────────────────────────────┐
│               Incremental Collection                  │
├──────────────────────────────────────────────────────┤
│  1. Query last crawl date from crawl_log             │
│  2. Build filter with from_publication_date          │
│  3. Fetch new papers only                            │
│  4. Deduplicate against existing papers              │
│  5. Save new papers to database                      │
│  6. Log crawl results                                │
└──────────────────────────────────────────────────────┘
```

**Estimated time**: ~5 minutes for 500 papers

## Filter Construction

```python
def build_filter(concepts, from_date=None):
    filters = [
        f"concepts.id:{concepts[0]}",  # Oncology
        "has_abstract:true",            # Required for RAG
        "type:article",                 # Journal articles only
    ]

    if from_date:
        filters.append(f"from_publication_date:{from_date}")

    return ",".join(filters)
```

## Progress Tracking

The scheduler tracks:

| Metric | Description |
|--------|-------------|
| `api_calls` | Total API requests made |
| `papers_fetched` | Papers returned by API |
| `papers_parsed` | Papers with valid abstract |
| `papers_saved` | Successfully saved to DB |
| `duplicates_skipped` | Already in database |
| `rate_limits` | 429 errors encountered |
| `errors` | Other errors |

## Cron Scheduling (Future)

Using APScheduler for production:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Daily at 2 AM
scheduler.add_job(
    run_incremental,
    CronTrigger.from_crontab("0 2 * * *"),
    id="daily_crawl"
)

scheduler.start()
```

## Error Handling

| Error | Action |
|-------|--------|
| 429 Rate Limit | Exponential backoff (1s → 2s → 4s) |
| Network Timeout | Retry up to 5 times |
| Parse Error | Log and skip paper |
| Database Error | Log and continue |

## Database Schema

Uses existing `papers` table from OAR-73:

```sql
CREATE TABLE papers (
    openalex_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    ...
    collected_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE crawl_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    papers_fetched INTEGER,
    papers_saved INTEGER,
    papers_skipped INTEGER,
    status VARCHAR(20)
);
```

## Usage Examples

```bash
# Test run (100 papers)
python batch_scheduler.py --mode test --papers 100

# Initial collection (5 years, ~50K papers)
python batch_scheduler.py --mode initial --years 5

# Incremental (since last crawl)
python batch_scheduler.py --mode incremental
```
