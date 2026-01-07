# OARIA Paper Crawler (HK)

Integrated paper crawler for oncology research papers using OpenAlex API.

## Components

| File | Feature | Description |
|------|---------|-------------|
| `openalex_client.py` | OAR-94 | OpenAlex API client |
| `models.py` | OAR-98 | Pydantic data models |
| `live_crawler.py` | OAR-99 | Live demo crawler with progress display |
| `batch_scheduler.py` | OAR-102 | Scheduled batch collection |
| `retry_handler.py` | OAR-101 | Exponential backoff retry logic |
| `deduplicator.py` | OAR-100 | Three-layer deduplication |
| `fulltext_extractor.py` | - | PDF full-text extraction |
| `app.py` | - | Streamlit frontend |

## Quick Start

```bash
# 1. Start PostgreSQL
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Streamlit app
streamlit run src/app.py

# 4. Or run CLI crawler
python src/live_crawler.py --papers 20
python src/batch_scheduler.py --mode test --papers 100
```

## Database

Connect with DBeaver:
- Host: `localhost`
- Port: `5432`
- Database: `oaria`
- User: `oaria`
- Password: `oaria123`

## Documentation

See `docs/` folder for detailed design documents:
- `OARIA_F02_F03_Specification.md` - Main specification
- `openalex-api-integration.md` - API integration details
- `postgresql-schema-design.md` - Database schema
- `scheduler-design.md` - Batch scheduler design
- `retry-logic.md` - Retry mechanism
- `deduplication-logic.md` - Deduplication strategy
