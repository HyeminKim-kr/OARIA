# OAR-21: Batch Crawler Scheduler

> **Owner**: hk (Hyemin Kim)
>
> **Sub-task**: OAR-102
>
> **Purpose**: Automate paper collection with scheduled batch crawling

---

## Features

| Feature | Description |
|---------|-------------|
| Initial Collection | Batch collect papers from the last 5 years |
| Daily Incremental | Daily collection of new papers only |
| Batch Size | Configurable (default 200 per request) |
| Cron Scheduling | Configurable schedule (e.g., daily at 2 AM) |
| Progress Logging | Track collection progress in real-time |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Batch Scheduler                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Cron      │───▶│   Crawler   │───▶│   Database  │     │
│  │  Scheduler  │    │   Manager   │    │   Writer    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                  │                  │             │
│         ▼                  ▼                  ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Schedule   │    │   OpenAlex  │    │  PostgreSQL │     │
│  │   Config    │    │     API     │    │             │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## Crawl Modes

### 1. Initial Collection (Backfill)

First-time setup: collect all oncology papers from the last 5 years.

```python
scheduler.run_initial_collection(
    years_back=5,
    batch_size=200,
    concepts=["C126322002"]  # Oncology
)
```

**Estimated volume**: ~50,000 papers

### 2. Daily Incremental

After initial collection, only fetch new papers published since last run.

```python
scheduler.run_incremental(
    since_date="2025-12-28",
    batch_size=200
)
```

**Estimated volume**: ~100-500 papers/day

---

## Schedule Configuration

```python
# Default schedule: Daily at 2:00 AM
schedule_config = {
    "initial": "0 2 * * *",      # Run once, then disable
    "incremental": "0 2 * * *",  # Daily at 2 AM
    "batch_size": 200,
    "concepts": ["C126322002"],  # Oncology
}
```

---

## Folder Structure

```
OAR-21/hk/
├── README.md                    # This file
├── docs/
│   └── scheduler-design.md      # Detailed design document
├── src/
│   ├── batch_scheduler.py       # Main scheduler implementation
│   └── crawl_manager.py         # Crawl job management
└── output/                      # Crawl logs
```

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Cron schedule configurable | Pending |
| Collection progress logging | Pending |
| Failure notifications | Pending |

---

## Integration

Uses components from:
- **OAR-94**: OpenAlex API client
- **OAR-100**: Deduplication logic
- **OAR-101**: Retry handling

---

## References

- [APScheduler Docs](https://apscheduler.readthedocs.io/) - Python scheduler library
- [OpenAlex Filters](https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/filter-entity-lists)
