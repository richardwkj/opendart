# Repository Guidelines

**Generated:** 2026-01-18 | **Commit:** 114a9c5 | **Branch:** main

## Overview
Korean Financial Data ETL - pulls company financials and events from Open DART API into PostgreSQL. Python 3.10+, SQLAlchemy 2.0, Click CLI.

## Structure
```
opendart/
├── src/opendart/        # Core package (see src/opendart/AGENTS.md)
│   ├── api.py           # DART client w/ rate limiting
│   ├── cli.py           # Click commands
│   ├── models.py        # 4 tables: companies, financials, events, progress
│   └── etl/             # Ingestion flows
├── alembic/versions/    # 001_initial_schema, 002_latest_financials_view
├── tests/               # pytest (minimal coverage)
└── spec.md              # Product specification
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Add CLI command | `src/opendart/cli.py` | Use `@cli.command()` decorator |
| New ETL flow | `src/opendart/etl/` | Follow pattern in `financials.py` |
| Schema change | `src/opendart/models.py` → `alembic revision --autogenerate` | Then `alembic upgrade head` |
| API wrapper | `src/opendart/api.py` | Add method to `DartClient` class |
| Rate limiting | `src/opendart/config.py` | `request_delay`, `rate_limit_pause` |

## Key Domain Concepts

| Term | Meaning |
|------|---------|
| `corp_code` | DART 8-digit company ID (PK, stable) |
| `stock_code` | KRX 6-digit ticker (can be reused after delisting) |
| `report_code` | 11013=Q1, 11012=Q2, 11014=Q3, 11011=Annual |
| `fs_div` | CFS (consolidated) or OFS (standalone) |
| `earliest_data_year` | Skip years before this (optimization) |

## Conventions

- Domain naming preserved: `corp_code`, `stock_code`, `report_code`, `fs_div` - match DART semantics
- PostgreSQL upserts via `ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE`
- All ETL functions return stats dict: `{"total_records": N, "errors": N, ...}`
- Session management: `with get_session() as session:` context manager

## Anti-Patterns

- **NEVER** use `stock_code` as FK - it gets reassigned after delisting
- **NEVER** commit secrets in `.env` 
- **NEVER** skip rate limiting - daily limit is 20,000 requests
- **NEVER** suppress type hints - project uses type annotations throughout

## Commands

```bash
# Development
uv sync                         # Install deps
uv run pytest tests/            # Run tests

# Database
uv run alembic upgrade head     # Apply migrations
uv run opendart init-db         # Create tables (dev only)

# ETL Operations
uv run opendart ingest-companies <csv>
uv run opendart backfill --priority-only --on-error-013=mark
uv run opendart sync-events --days=31
uv run opendart run-scheduler   # Monthly automation

# Migrations
uv run alembic revision --autogenerate -m "description"
```

## API Constraints

| Constraint | Value |
|------------|-------|
| Daily limit | 20,000 requests |
| Throttle delay | 0.15s between requests |
| Data availability | 2015 Q1 onwards |
| Error 013 | No data for company/period |
| Error 020 | Rate limit exceeded |

## Notes

- `backfill_progress` table enables resumable backfill after rate limits
- `earliest_data_year` on Company prevents wasteful queries for companies with no early data
- `--on-error-013=mark` mode auto-discovers when company data starts
- Monthly scheduler runs 1st of month at 02:00 KST
