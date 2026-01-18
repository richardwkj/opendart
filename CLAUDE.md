# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean Financial Data Automator - an ETL system that pulls financial fundamentals and corporate events for Korean listed companies from the Open DART API and stores them in a relational database.

## Tech Stack

- Python 3.10+
- OpenDartReader library (wraps Open DART API)
- PostgreSQL (recommended), MySQL, or SQLite
- SQLAlchemy 2.0+ with Alembic for migrations
- Click for CLI
- APScheduler for automated monthly syncs

## Project Structure

```
src/opendart/
├── __init__.py       # Package init with version
├── config.py         # Environment config loader
├── db.py             # Database session management
├── models.py         # SQLAlchemy ORM models
├── api.py            # DART API client with rate limiting
├── cli.py            # Click CLI entry point
├── scheduler.py      # APScheduler for monthly automation
├── notifications.py  # Email notification system
└── etl/
    ├── __init__.py
    ├── companies.py  # Company CSV ingestion/delisting
    ├── financials.py # Financial data ETL + backfill
    └── events.py     # Key events ETL
```

## CLI Commands

Run with `uv run opendart <command>` or `python -m opendart.cli <command>`:

- `init-db` - Create database tables from SQLAlchemy models
- `ingest-companies <csv>` - Import companies from CSV (requires `corp_code`, `corp_name`)
  - `--on-stock-code-reuse=reassign|reject` - Handle stock code conflicts
  - `--default-priority/--no-default-priority` - Set priority flag
- `update-delistings <csv>` - Apply delisting dates from CSV (requires `corp_code`, `delisted_date`)
- `backfill` - Backfill financial data from DART API
  - `--corp-code` - Single company
  - `--start-year` - Default 2015
  - `--priority-only` - Only priority companies
  - `--on-error-013=skip|mark|stop` - Handle no-data errors (mark sets `earliest_data_year`)
  - `--on-rate-limit=pause|exit|prompt` - Handle rate limits (pause waits 1hr)
- `sync-events` - Sync key events from past N days
  - `--days` - Lookback period (default 31)
- `run-scheduler` - Start APScheduler for automated monthly syncs (1st of month at 02:00 KST)
- `run-sync` - Manually trigger monthly sync job

## Key Domain Concepts

- **corp_code**: DART's 8-digit company identifier (stable, used as PK) - more reliable than stock_code which can be reused after delisting
- **stock_code**: 6-digit KRX ticker (may be reused)
- **report_code**: Quarterly identifier - `11013` (Q1), `11012` (Q2), `11014` (Q3), `11011` (Q4/Annual)
- **fs_div**: Financial statement division - `CFS` (consolidated) or `OFS` (standalone)
- **earliest_data_year**: Tracked per company to avoid wasteful queries for years without data

## Database Schema

Four tables with `corp_code` as the linking key:
- `companies` (master) - company identifiers, listing/delisting dates, priority flag, earliest_data_year
- `financial_fundamentals` (detail) - financial statement line items with versioning for restatements
- `key_events` (detail) - disclosures keyed by `rcept_no`
- `backfill_progress` - checkpoint table for resumable backfill

View: `latest_financials` - shows only the most recent version of each financial entry.

## Alembic Migrations

Migrations in `alembic/versions/`:
- `001_initial_schema.py` - all tables
- `002_latest_financials_view.py` - Latest_Financials view

Run migrations: `uv run alembic upgrade head`

## API Constraints

- **Daily limit**: 20,000 requests
- **Throttling**: 0.15s delay between requests
- **Data availability**: `finstate_all()` available from 2015 Q1 onwards
- **Error codes**: 010 (unregistered key), 011 (expired), 013 (no data), 020 (rate limit), 800 (data doesn't exist)

## Configuration

API keys and database credentials stored in `.env` file (gitignored). See `.env.example` for template.

Required:
- `DART_API_KEY` - Open DART API key
- `DATABASE_URL` - PostgreSQL connection string

Optional (for email notifications):
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `NOTIFICATION_EMAIL` - recipient for alerts

## Running Tests

```bash
uv run pytest tests/
```
