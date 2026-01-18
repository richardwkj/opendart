# OpenDART ETL

Korean Financial Data Automator - ETL system that pulls financial fundamentals and corporate events for Korean listed companies from the [Open DART API](https://opendart.fss.or.kr/) and stores them in a relational database.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI (cli.py)                              │
│  Entry point for all commands: backfill, sync-events, etc.          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │ companies.py│ │financials.py│ │  events.py  │
            │  (ETL)      │ │   (ETL)     │ │   (ETL)     │
            └─────────────┘ └─────────────┘ └─────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                            ┌─────────────┐
                            │   api.py    │
                            │ DartClient  │
                            │ (rate limit)│
                            └─────────────┘
                                    │
                                    ▼
                            ┌─────────────┐
                            │OpenDartReader│
                            │  (Library)  │
                            └─────────────┘
                                    │
                                    ▼
                            ┌─────────────┐
                            │  DART API   │
                            │ (External)  │
                            └─────────────┘

        ┌───────────────────────────────────────────┐
        │              Database Layer               │
        │  ┌─────────┐  ┌─────────┐  ┌───────────┐ │
        │  │models.py│  │  db.py  │  │ Alembic   │ │
        │  │ (ORM)   │  │(Session)│  │(Migrations)│ │
        │  └─────────┘  └─────────┘  └───────────┘ │
        └───────────────────────────────────────────┘
```

## Module Descriptions

### Core Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | Command-line interface using Click. Entry point for all operations. |
| `config.py` | Loads environment variables from `.env` file (API key, database URL). |
| `db.py` | SQLAlchemy session management. Provides `get_session()` context manager. |
| `models.py` | ORM models: `Company`, `FinancialFundamental`, `KeyEvent`, `BackfillProgress`. |
| `api.py` | `DartClient` class wrapping OpenDartReader with rate limiting (0.15s delay). |

### ETL Modules (`etl/`)

| Module | Purpose |
|--------|---------|
| `companies.py` | Ingests company master data from CSV, handles delistings. |
| `financials.py` | Fetches financial statements via `finstate_all()`, inserts into DB. |
| `events.py` | Fetches disclosure events via `list()`, filters for key events. |

### Automation Modules

| Module | Purpose |
|--------|---------|
| `scheduler.py` | APScheduler-based monthly automation (1st of month at 02:00 KST). |
| `notifications.py` | Email alerts for job failures/completions. |

## Data Flow: Step-by-Step

### Step 1: Initialize Database
```
cli.py (init-db)
    → db.py (init_db)
    → models.py (creates tables via SQLAlchemy)
```

Or use Alembic migrations:
```
alembic upgrade head
    → alembic/versions/*.py
    → Database tables created
```

### Step 2: Load Companies
```
cli.py (ingest-companies)
    → etl/companies.py (ingest_companies_from_csv)
    → db.py (session)
    → models.py (Company)
    → Database: companies table
```

Companies must be loaded first because financial data references `corp_code` as a foreign key.

### Step 3: Backfill Financial Data
```
cli.py (backfill)
    → etl/financials.py (backfill_company)
    → api.py (DartClient.finstate_all)
    → OpenDartReader library
    → DART API (external)
    → Parse response
    → db.py (session)
    → models.py (FinancialFundamental)
    → Database: financial_fundamentals table
```

The backfill iterates through years (2015 to present) and quarters (Q1-Q4) for each company.

### Step 4: Sync Events
```
cli.py (sync-events)
    → etl/events.py (sync_recent_events)
    → api.py (DartClient.list)
    → DART API
    → Filter for key events (kind='B')
    → Database: key_events table
```

### Step 5: Automated Monthly Sync (Optional)
```
cli.py (run-scheduler)
    → scheduler.py (run_scheduler)
    → APScheduler (CronTrigger: 1st of month, 02:00 KST)
    → scheduler.py (monthly_sync_job)
    → etl/financials.py + etl/events.py
    → notifications.py (on success/failure)
```

## Execution Methods

### Method 1: Using uv (Development)
```bash
# With uv package manager
uv run opendart <command>

# Examples
uv run opendart init-db
uv run opendart ingest-companies companies.csv
uv run opendart backfill --corp-code 00126380 --start-year 2024
uv run opendart sync-events --days 7
```

### Method 2: Direct Python Module
```bash
# Activate virtual environment first
source .venv/bin/activate

# Run as module
python -m opendart.cli <command>

# Examples
python -m opendart.cli backfill --start-year 2023
python -m opendart.cli sync-events
```

### Method 3: Installed Package
```bash
# Install the package
pip install -e .

# Now 'opendart' command is available globally
opendart init-db
opendart backfill --corp-code 00126380
opendart sync-events --days 31
```

### Method 4: Using Alembic Directly
```bash
# For database migrations
uv run alembic upgrade head    # Apply all migrations
uv run alembic downgrade -1    # Rollback one migration
uv run alembic current         # Show current revision

# Or with activated venv
alembic upgrade head
```

## Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd opendart
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your DART_API_KEY and DATABASE_URL

# 3. Create database tables
uv run alembic upgrade head

# 4. Load companies (create a CSV with corp_code, corp_name, stock_code)
uv run opendart ingest-companies your_companies.csv

# 5. Backfill financial data
uv run opendart backfill --start-year 2024

# 6. Sync recent events
uv run opendart sync-events --days 31
```

## Database Schema

```
┌─────────────────┐       ┌──────────────────────────┐
│   companies     │       │  financial_fundamentals  │
├─────────────────┤       ├──────────────────────────┤
│ corp_code (PK)  │◄──────│ corp_code (FK)           │
│ stock_code      │       │ year                     │
│ corp_name       │       │ report_code              │
│ is_priority     │       │ fs_div (CFS/OFS)         │
│ listing_date    │       │ account_id               │
│ delisted_date   │       │ account_name             │
│ earliest_data_yr│       │ amount                   │
└─────────────────┘       │ version                  │
        │                 └──────────────────────────┘
        │
        │                 ┌──────────────────────────┐
        └────────────────►│      key_events          │
                          ├──────────────────────────┤
                          │ rcept_no (PK)            │
                          │ corp_code (FK)           │
                          │ report_nm                │
                          │ event_date               │
                          └──────────────────────────┘

┌─────────────────────────┐
│   backfill_progress     │  (Checkpoint table for resumable backfill)
├─────────────────────────┤
│ corp_code               │
│ year                    │
│ report_code             │
│ status                  │
│ error_message           │
└─────────────────────────┘

┌─────────────────────────┐
│   latest_financials     │  (VIEW - shows only latest version per entry)
└─────────────────────────┘
```

## CLI Commands Reference

| Command | Description |
|---------|-------------|
| `init-db` | Create tables from SQLAlchemy models (alternative to Alembic) |
| `ingest-companies <csv>` | Load company master data |
| `update-delistings <csv>` | Apply delisting dates |
| `backfill` | Fetch financial statements from DART API |
| `sync-events` | Fetch recent disclosure events |
| `run-scheduler` | Start automated monthly sync daemon |
| `run-sync` | Manually trigger monthly sync job |

## Configuration

Create `.env` file:
```env
DART_API_KEY=your_api_key_here
DATABASE_URL=postgresql:///opendart_updater

# Optional: Email notifications
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=password
NOTIFICATION_EMAIL=alerts@example.com
```

## API Rate Limits

- **Daily limit**: 20,000 requests
- **Throttling**: 0.15s delay between requests (enforced by `DartClient`)
- **Rate limit handling**: `--on-rate-limit=pause|exit|prompt`
