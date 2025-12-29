# OAR-23: Duplicate Paper Detection & Removal Logic

> **Owner**: hk (Hyemin Kim)
>
> **Sub-task**: OAR-100
>
> **Purpose**: Prevent duplicate papers from being stored in the database

---

## Original Spec vs ADR Decision

### Original Requirement (OAR-23)

The original task specified:
- **PMID-based** duplicate check
- Batch filtering before storage
- Update option for existing papers

### ADR-001 Change: OpenAlex ID instead of PMID

Per ADR-001, we use **OpenAlex** instead of PubMed. This changes the deduplication key:

| Aspect | Original (PubMed) | ADR Decision (OpenAlex) |
|--------|-------------------|-------------------------|
| Primary Key | PMID | OpenAlex ID |
| Availability | May be null | Always present |
| Coverage | PubMed papers only | ALL papers (250M+) |
| Secondary Key | DOI | DOI (same) |

**Why this is actually better:**
- OpenAlex ID exists for ALL papers, not just PubMed-indexed ones
- No null handling needed - every paper has an ID
- Already used as PRIMARY KEY in our schema (OAR-73)

**Trade-off:**
- None significant. PMID can still be stored for cross-reference.

---

## Implementation Status: NEW CODE

Unlike OAR-19, this task required new implementation.

### Location

```
spikes/OAR-23/hk/src/deduplicator.py
└── Deduplicator class
```

### Three-Layer Defense

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Layer 1 | Pre-filter in memory | Efficiency (O(1) set lookup) |
| Layer 2 | ON CONFLICT clause | Handle race conditions |
| Layer 3 | PRIMARY KEY constraint | Last line of defense |

---

## Deduplication Logic Breakdown

### Step 1: Get Existing IDs

```python
async def get_existing_ids(self) -> set[str]:
    """Fetch all OpenAlex IDs from database. Returns set for O(1) lookup."""
    query = "SELECT openalex_id FROM papers"
    rows = await self.db.fetch_all(query)
    return {row["openalex_id"] for row in rows}
```

### Step 2: Filter New Papers

```python
def filter_new_papers(self, papers: list[Paper], existing_ids: set[str]) -> tuple[list[Paper], int]:
    """Filter out papers that already exist."""
    new_papers = []
    duplicate_count = 0

    for paper in papers:
        if paper.openalex_id in existing_ids:
            duplicate_count += 1
        else:
            new_papers.append(paper)

    return new_papers, duplicate_count
```

### Step 3: Batch Insert with Conflict Handling

```sql
INSERT INTO papers (openalex_id, title, abstract, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT (openalex_id) DO NOTHING;
-- OR for updates:
ON CONFLICT (openalex_id) DO UPDATE SET
    cited_by_count = EXCLUDED.cited_by_count;
```

---

## Folder Structure

```
OAR-23/hk/
├── README.md                    # This file
├── docs/
│   └── deduplication-logic.md   # Detailed design document
├── src/
│   └── deduplicator.py          # Deduplication implementation
└── output/                      # Test outputs
```

---

## Test Results

```
Total papers from API: 3
Existing IDs in DB: {W001, W003}
New papers: 1 (W002)
Duplicates skipped: 2 (W001, W003)
```

---

## Acceptance Criteria Status

| Criteria | Original | Status |
|----------|----------|--------|
| 0 duplicate PMIDs | → 0 duplicate OpenAlex IDs | ✅ PRIMARY KEY + pre-filter |
| Bulk dedup performance | Same requirement | ✅ Set-based O(1) lookup |
| Update option | Same requirement | ✅ ON CONFLICT DO UPDATE |

---

## References

- [OAR-73 Schema](../../OAR-20/hk/) - PostgreSQL PRIMARY KEY constraint
- [OAR-94 Crawler](../../OAR-18/hk/src/openalex_client.py) - Paper model
- [Detailed Design](./docs/deduplication-logic.md) - Full design document
- [ADR-001 in CLAUDE.md](../../../../claude.md) - OpenAlex decision
