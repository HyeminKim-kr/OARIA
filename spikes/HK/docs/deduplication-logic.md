# Deduplication Logic Design

> **Task**: OAR-100 (sub-task of OAR-23)
>
> **Owner**: Hyemin Kim (AI Lead)
>
> **Version**: v1.0 (2025-12-28)

---

## ADR Compliance

This implementation follows ADR-001 from `CLAUDE.md`:

| ADR | Decision | Implementation |
|-----|----------|----------------|
| ADR-001 | OpenAlex over PubMed | `openalex_id` as dedup key instead of PMID |
| ADR-007 | Async-first | `async/await` pattern for DB operations |

---

## Original Spec vs ADR Decision

### Original Requirement (OAR-23)

```
PMID-based duplicate check:
- Check if PMID exists before insert
- Batch filtering before storage
- Update option for existing papers
- Acceptance: 0 duplicate PMIDs guaranteed
```

### ADR-001 Change

| Aspect | Original (PubMed) | ADR Decision (OpenAlex) |
|--------|-------------------|-------------------------|
| Primary Dedup Key | PMID | `openalex_id` |
| Key Format | Numeric string | `W{number}` (e.g., W2741809807) |
| Availability | May be null | Always present |
| Secondary Key | DOI | DOI (same) |

### Why This is Actually Better

1. **100% key availability** - Every OpenAlex paper has an ID
2. **Schema consistency** - `openalex_id` is already our PRIMARY KEY (OAR-73)
3. **No null handling** - PMID can be null for non-PubMed papers
4. **Simpler logic** - One key to check, not two

### Trade-off

None significant. PMID can still be stored and used for cross-reference.

---

## Deduplication Scenarios

### Scenario 1: Initial Crawl

```
Database: Empty
Crawl: Papers [A, B, C]
Action: Insert all
Result: Database has [A, B, C]
```

### Scenario 2: Re-crawl (Same Query)

```
Database: [A, B, C]
Crawl: Papers [A, B, C]  # Same papers fetched
Action: Pre-filter removes all (already exist)
Result: Database unchanged, 0 inserts
```

### Scenario 3: Incremental Crawl (New Papers)

```
Database: [A, B, C]
Crawl: Papers [C, D, E]  # C is duplicate
Action: Pre-filter removes C, insert D, E
Result: Database has [A, B, C, D, E]
```

### Scenario 4: Update Existing (Upsert)

```
Database: [A (citations=10), B, C]
Crawl: Papers [A (citations=15)]  # Same paper, updated metadata
Action: ON CONFLICT DO UPDATE (citations=15)
Result: Paper A updated with new citation count
```

---

## Implementation Details

### Deduplicator Class

```python
class Deduplicator:
    """
    Handles paper deduplication before database insertion.

    Usage:
        deduplicator = Deduplicator(db_connection)

        # Get existing IDs (one query)
        existing_ids = await deduplicator.get_existing_ids()

        # Filter papers
        new_papers = deduplicator.filter_new_papers(papers, existing_ids)

        # Or use convenience method
        new_papers = await deduplicator.filter_duplicates(papers)
    """
```

### Method 1: Get Existing IDs

```python
async def get_existing_ids(self) -> set[str]:
    """
    Fetch all OpenAlex IDs from database.

    Returns:
        Set of existing openalex_ids for O(1) lookup

    Performance:
        - Single query regardless of table size
        - 50,000 IDs ≈ 1 MB memory
        - Query time: < 100ms for 50K rows
    """
    query = "SELECT openalex_id FROM papers"
    rows = await self.db.fetch_all(query)
    return {row["openalex_id"] for row in rows}
```

### Method 2: Filter New Papers

```python
def filter_new_papers(
    self,
    papers: list[Paper],
    existing_ids: set[str]
) -> tuple[list[Paper], int]:
    """
    Filter out papers that already exist.

    Args:
        papers: Papers from API
        existing_ids: Set of existing openalex_ids

    Returns:
        (new_papers, duplicate_count)

    Performance:
        - O(n) where n = len(papers)
        - Each lookup is O(1) with set
    """
    new_papers = []
    duplicate_count = 0

    for paper in papers:
        if paper.openalex_id in existing_ids:
            duplicate_count += 1
        else:
            new_papers.append(paper)

    return new_papers, duplicate_count
```

### Method 3: Batch Insert with Conflict Handling

```python
async def batch_insert(
    self,
    papers: list[Paper],
    on_conflict: str = "DO NOTHING"
) -> int:
    """
    Insert papers with duplicate handling.

    Args:
        papers: Papers to insert
        on_conflict: "DO NOTHING" or "DO UPDATE SET ..."

    Returns:
        Number of rows inserted
    """
    query = f"""
        INSERT INTO papers (openalex_id, title, abstract, ...)
        VALUES ($1, $2, $3, ...)
        ON CONFLICT (openalex_id) {on_conflict}
    """

    inserted = 0
    for paper in papers:
        try:
            await self.db.execute(query, paper.model_dump())
            inserted += 1
        except Exception as e:
            logger.warning("insert_failed", paper=paper.openalex_id, error=str(e))

    return inserted
```

---

## DOI-Based Secondary Dedup

### Why DOI as Secondary Key?

| Scenario | OpenAlex ID | DOI | Solution |
|----------|-------------|-----|----------|
| Normal | W123 | 10.1000/abc | Dedup by openalex_id |
| Same paper, different source | W123 vs W456 | Same DOI | Dedup by DOI |
| No DOI | W789 | null | Dedup by openalex_id only |

### Implementation

```sql
-- Create unique index on DOI (excluding nulls)
CREATE UNIQUE INDEX idx_papers_doi
ON papers(doi)
WHERE doi IS NOT NULL;
```

```python
async def check_doi_duplicate(self, doi: str) -> bool:
    """Check if DOI already exists (secondary dedup)."""
    if not doi:
        return False
    query = "SELECT 1 FROM papers WHERE doi = $1 LIMIT 1"
    result = await self.db.fetch_one(query, doi)
    return result is not None
```

---

## Performance Benchmarks

### Expected Performance

| Operation | 1,000 papers | 10,000 papers | 50,000 papers |
|-----------|-------------|---------------|---------------|
| Get existing IDs | ~10ms | ~50ms | ~100ms |
| Filter in memory | ~1ms | ~5ms | ~25ms |
| Batch insert (new) | ~500ms | ~5s | ~25s |

### Memory Usage

| Papers in DB | ID Set Size | Memory |
|--------------|-------------|--------|
| 1,000 | 1,000 | ~20 KB |
| 10,000 | 10,000 | ~200 KB |
| 50,000 | 50,000 | ~1 MB |

Memory is minimal - set-based dedup is the right choice.

---

## Error Handling

### Duplicate Insert Error

```python
try:
    await self.db.execute(insert_query, paper)
except UniqueViolationError:
    # This happens if:
    # 1. Race condition between pre-filter and insert
    # 2. Pre-filter cache was stale
    logger.info("duplicate_skipped", paper=paper.openalex_id)
    # Not an error - expected in concurrent scenarios
```

### Connection Errors

```python
async def get_existing_ids_with_retry(self, max_retries: int = 3) -> set[str]:
    """Fetch existing IDs with retry logic."""
    for attempt in range(max_retries):
        try:
            return await self.get_existing_ids()
        except ConnectionError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

---

## Integration with Crawler

### In `openalex_client.py` or `crawler.py`:

```python
async def crawl_and_store(config: CrawlerConfig):
    """Crawl papers and store with deduplication."""

    deduplicator = Deduplicator(db)

    # Get existing IDs once at start
    existing_ids = await deduplicator.get_existing_ids()
    logger.info("existing_papers", count=len(existing_ids))

    async with OpenAlexClient(email=config.email) as client:
        async for batch in client.search_papers(config):
            # Filter duplicates
            new_papers, dup_count = deduplicator.filter_new_papers(batch, existing_ids)

            if new_papers:
                # Insert new papers
                inserted = await deduplicator.batch_insert(new_papers)

                # Update cache for next batch
                existing_ids.update(p.openalex_id for p in new_papers)

                logger.info(
                    "batch_processed",
                    total=len(batch),
                    duplicates=dup_count,
                    inserted=inserted
                )
```

---

## Acceptance Criteria Status

| Criteria | Original | Implementation | Status |
|----------|----------|----------------|--------|
| 0 duplicate PMIDs | → 0 duplicate OpenAlex IDs | PRIMARY KEY + pre-filter | ✅ Designed |
| Bulk dedup performance | Same | Set-based O(1) lookup | ✅ Designed |
| Update option | Same | ON CONFLICT DO UPDATE | ✅ Designed |

---

## References

- [OAR-73 Schema](../../../OAR-20/hk/) - PostgreSQL PRIMARY KEY constraint
- [OAR-94 Crawler](../../../OAR-18/hk/src/openalex_client.py) - Paper model & crawling
- [PostgreSQL ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
- [ADR-001 in CLAUDE.md](../../../../../claude.md) - OpenAlex decision
