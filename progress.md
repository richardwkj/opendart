# Progress

Based on `docs/spec.md` and `CLAUDE.md`, this checklist tracks what is implemented versus still needed.

## Completed

- [x] Project structure with `uv` package manager and `pyproject.toml`
- [x] Configuration loader for `.env` (`DART_API_KEY`, `DATABASE_URL`, SMTP settings) in `src/opendart/config.py`
- [x] Database session management in `src/opendart/db.py`
- [x] DART API wrapper with rate limiting (0.15s delay) and error handling in `src/opendart/api.py`
- [x] Core database models in `src/opendart/models.py`:
  - `Company` (master table with corp_code PK, includes `earliest_data_year`)
  - `FinancialFundamental` (with composite unique constraint)
  - `KeyEvent` (with rcept_no PK)
  - `BackfillProgress` (checkpoint table for resumable backfill)
- [x] Financial ETL transforms + PostgreSQL upsert logic in `src/opendart/etl/financials.py`
- [x] Events ETL transforms + upsert logic in `src/opendart/etl/events.py`
- [x] Company ingestion module in `src/opendart/etl/companies.py`:
  - CSV parsing with date/boolean/code normalization
  - Duplicate detection (in-file and in-database)
  - Stock code reuse policy (`reassign` or `reject`)
  - Delisting updates from CSV
- [x] Alembic migrations in `alembic/versions/`:
  - `001_initial_schema.py` - all tables including `earliest_data_year`
  - `002_latest_financials_view.py` - `Latest_Financials` view per spec 4.2.2
- [x] CLI entry point in `src/opendart/cli.py` with commands:
  - `init-db` - create tables via SQLAlchemy
  - `ingest-companies` - CSV import with stock code reuse flag
  - `update-delistings` - apply delisting dates
  - `backfill` - financial data backfill with progress tracking
    - `--on-error-013=skip|mark|stop` - handle no-data errors (mark sets `earliest_data_year`)
    - `--on-rate-limit=pause|exit|prompt` - handle rate limits per spec 5.2
  - `sync-events` - sync key events from past N days
  - `run-scheduler` - start APScheduler for automated monthly syncs
  - `run-sync` - manually trigger monthly sync job
- [x] Monthly scheduler in `src/opendart/scheduler.py`:
  - APScheduler with cron trigger (1st of month at 02:00 KST)
  - `monthly_sync_job()` for automated data sync
- [x] Notification system in `src/opendart/notifications.py`:
  - Email alerts for job failures and completions
  - Configurable via SMTP_* and NOTIFICATION_EMAIL env vars
- [x] Initial pytest coverage:
  - `tests/test_companies_ingest.py` - company ingestion, stock code reuse, delistings
  - `tests/test_financials_helpers.py` - parse_amount, transform_financial_data

## Not Started / Missing vs Spec

- [ ] Tests for scheduler and notification modules
- [ ] Tests for events ETL module
- [ ] Tests for API client (would need mocking)
- [ ] Integration tests for backfill command
- [ ] GitHub Actions workflow for CI/CD or scheduled runs
