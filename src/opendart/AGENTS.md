# src/opendart Package

## Overview
Core ETL package: DART API client, ORM models, CLI, and data flows.

## Module Responsibilities

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `api.py` | DART API wrapper | `DartClient`, `DartError`, `DartErrorCode` |
| `models.py` | ORM definitions | `Company`, `FinancialFundamental`, `KeyEvent`, `BackfillProgress` |
| `db.py` | Session management | `get_session()`, `get_engine()` |
| `config.py` | Environment config | `get_settings()` → loads from `.env` |
| `cli.py` | Click entry point | `cli` group + all commands |
| `scheduler.py` | APScheduler jobs | `run_scheduler()`, `monthly_sync_job()` |
| `notifications.py` | Email alerts | SMTP integration |

## ETL Subpackage (`etl/`)

| Module | Flow | Entry Point |
|--------|------|-------------|
| `companies.py` | CSV → Company table | `ingest_companies_from_csv()`, `apply_delisting_updates_from_csv()` |
| `financials.py` | DART API → financial_fundamentals | `backfill_company()`, `fetch_company_financials()` |
| `events.py` | DART API → key_events | `sync_recent_events()`, `fetch_all_events()` |

## Patterns

### Rate Limiting
```python
# In api.py - DartClient._wait_for_rate_limit()
# Auto-throttles 0.15s between calls
client = DartClient()  # Gets settings from config
df = client.finstate_all(corp_code, year, report_code)
```

### Database Sessions
```python
# Always use context manager
with get_session() as session:
    result = session.execute(query)
    # Auto-commits on exit, rollbacks on exception
```

### PostgreSQL Upserts
```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(Model).values(records)
stmt = stmt.on_conflict_do_nothing(index_elements=["pk_col"])
# OR
stmt = stmt.on_conflict_do_update(index_elements=["pk_col"], set_={...})
```

### ETL Return Pattern
All ETL functions return stats dict:
```python
return {
    "total_records": N,
    "successful": N,
    "skipped": N,
    "errors": N,
    "rate_limited": bool  # financials only
}
```

## Error Handling

| DartErrorCode | Meaning | Typical Action |
|---------------|---------|----------------|
| `NO_DATA` (013) | No data exists | Skip or mark `earliest_data_year` |
| `RATE_LIMIT` (020) | Daily limit hit | Pause 1hr or exit |
| `DATA_NOT_EXIST` (800) | Invalid request | Log and skip |

## Where to Add

| Task | File | Pattern |
|------|------|---------|
| New DART endpoint | `api.py` | Copy `finstate_all()` pattern |
| New table | `models.py` | Extend `Base`, add migration |
| New ETL flow | `etl/*.py` | Return stats dict, use upserts |
| New CLI command | `cli.py` | `@cli.command()` + call ETL |
