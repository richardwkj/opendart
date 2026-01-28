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

## Web Dashboard (Next.js)

### Overview
A Next.js web application deployed on Vercel to visualize the collected DART financial data. Located in `web/` directory.

### Tech Stack
- Next.js 14+ (App Router)
- TypeScript
- Tailwind CSS for styling
- Prisma ORM (connects to existing PostgreSQL)
- shadcn/ui components

### Structure
```
web/
├── app/
│   ├── layout.tsx          # Root layout with providers
│   ├── page.tsx            # Home page - company search
│   ├── companies/
│   │   └── [corpCode]/
│   │       └── page.tsx    # Company detail with financials
│   └── api/
│       ├── companies/
│       │   └── route.ts    # GET /api/companies - list/search
│       └── financials/
│           └── [corpCode]/
│               └── route.ts # GET /api/financials/:corpCode
├── components/
│   ├── company-search.tsx  # Search input with autocomplete
│   ├── company-table.tsx   # Paginated company list
│   └── financial-table.tsx # Financial statement display
├── lib/
│   └── prisma.ts           # Prisma client singleton
└── prisma/
    └── schema.prisma       # Prisma schema (introspected from existing DB)
```

### Development Commands
```bash
cd web
npm install
npm run dev           # Start dev server on localhost:3000
npx prisma db pull    # Introspect existing database schema
npx prisma generate   # Generate Prisma client
```

### Deployment
Deployed on Vercel with the following environment variables:
- `DATABASE_URL` - PostgreSQL connection string (same as ETL uses)

### Key Features
1. **Company Search**: Full-text search by company name or stock code
2. **Company List**: Paginated table with sorting
3. **Financial Statements**: View financial line items by year/quarter
   - Filter by fs_div (CFS/OFS)
   - Filter by report_code (Q1/Q2/Q3/Annual)

### API Routes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/companies` | GET | List companies with search, pagination |
| `/api/companies?search=삼성` | GET | Search by name |
| `/api/financials/[corpCode]` | GET | Get financials for a company |
| `/api/financials/[corpCode]?year=2024&report_code=11011` | GET | Filter by year/quarter |

### Database Schema Notes for Frontend
The Prisma schema will map to existing tables:
- `companies` → Company model (PK: `corp_code`)
- `financial_fundamentals` → FinancialFundamental model (FK: `corp_code`)
- `key_events` → KeyEvent model (FK: `corp_code`)

**Important**: Use `corp_code` (not `stock_code`) for all relationships - stock codes can be reused after delisting.

## Common Pitfalls

### OpenDartReader Import
`OpenDartReader` is a class, not a module. Use directly:
```python
import OpenDartReader
dart = OpenDartReader(api_key)  # Correct
# NOT: OpenDartReader.OpenDartReader(api_key)
```

### DART API Field Sizes
DART returns longer values than expected. Key field sizes:
- `account_id`: up to 145 chars (e.g., `ifrs-full_NoncontrollingInterestsInSubsidiaries`)
- `account_name`: Korean names, allow 255 chars

### PostgreSQL Socket Connection
When using peer authentication (socket), the OS user must match the DB role:
```
DATABASE_URL=postgresql:///opendart_updater  # Uses current OS user
```
If connecting as different user, create a matching PostgreSQL role:
```sql
CREATE ROLE your_os_user WITH LOGIN SUPERUSER;
```

### Vercel DATABASE_URL Format
When setting `DATABASE_URL` in Vercel environment variables, ensure:
1. URL starts with `postgresql://` or `postgres://` protocol
2. Includes all required parameters for cloud databases

**Correct format for Neon:**
```
postgresql://user:password@host/dbname?sslmode=require
```

**Common error:**
```
Error validating datasource `db`: the URL must start with the protocol `postgresql://`
```
This means the DATABASE_URL is malformed or missing the protocol prefix.

### Radix UI Select Empty Values
Radix UI Select component does NOT support empty string `""` as a value. This causes client-side hydration errors.

**Wrong:**
```tsx
const [value, setValue] = useState("");  // Empty string initial
<SelectItem value="">All</SelectItem>    // Empty string value
```

**Correct:**
```tsx
const [value, setValue] = useState<string | undefined>(undefined);  // Use undefined
<SelectItem value="all">All</SelectItem>  // Use "all" sentinel value

// Then check for sentinel in logic:
if (value && value !== "all") {
  // Apply filter
}
```
