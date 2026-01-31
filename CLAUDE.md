# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Korean Financial Data Automator** - an ETL system that pulls financial fundamentals, corporate events, and XBRL disclosures for Korean listed companies from the Open DART API and stores them in a PostgreSQL database. Includes a Next.js web dashboard for data visualization.

## Tech Stack

### Backend (Python ETL)
- Python 3.10+
- OpenDartReader library (wraps Open DART API)
- SQLAlchemy 2.0+ with Alembic for migrations
- PostgreSQL (primary), MySQL, or SQLite
- Click for CLI
- APScheduler for automated monthly syncs
- Arelle for XBRL parsing

### Frontend (Next.js Dashboard)
- Next.js 16+ (App Router)
- React 19
- TypeScript
- Tailwind CSS 4
- Prisma ORM (connects to existing PostgreSQL)
- shadcn/ui components (Radix UI primitives)

## Project Structure

```
opendart/
├── src/opendart/           # Python ETL package
│   ├── __init__.py         # Package init with version
│   ├── config.py           # Environment config loader
│   ├── db.py               # Database session management
│   ├── models.py           # SQLAlchemy ORM models (5 tables)
│   ├── api.py              # DART API client with rate limiting
│   ├── cli.py              # Click CLI entry point (9 commands)
│   ├── scheduler.py        # APScheduler for monthly automation
│   ├── notifications.py    # Email notification system
│   └── etl/
│       ├── __init__.py
│       ├── companies.py    # Company CSV ingestion/delisting
│       ├── financials.py   # Financial data ETL + backfill
│       ├── events.py       # Key events ETL
│       └── xbrl.py         # XBRL text block ingestion
├── web/                    # Next.js dashboard
│   ├── app/                # App Router pages
│   │   ├── layout.tsx      # Root layout
│   │   ├── page.tsx        # Home page with company list
│   │   ├── companies/[corpCode]/page.tsx  # Company detail
│   │   └── api/            # API routes
│   │       ├── companies/route.ts
│   │       └── financials/[corpCode]/route.ts
│   ├── components/         # React components
│   │   ├── company-search.tsx
│   │   ├── company-table.tsx
│   │   ├── financial-table.tsx
│   │   └── ui/             # shadcn/ui components
│   ├── lib/prisma.ts       # Prisma client singleton
│   └── prisma/schema.prisma
├── alembic/                # Database migrations
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_latest_financials_view.py
│       └── 1af33ea2791c_create_financial_notes.py
├── tests/                  # Pytest tests
├── pyproject.toml          # Python dependencies (uv/hatch)
└── .env.example            # Environment template
```

## CLI Commands

Run with `uv run opendart <command>` or `python -m opendart.cli <command>`:

| Command | Description |
|---------|-------------|
| `init-db` | Create database tables from SQLAlchemy models |
| `ingest-companies <csv>` | Import companies from CSV (requires `corp_code`, `corp_name`) |
| `update-delistings <csv>` | Apply delisting dates from CSV |
| `import-by-stock-code <csv>` | Import by stock code (looks up corp_code from DART API) |
| `backfill` | Backfill financial data from DART API |
| `sync-events` | Sync key events from past N days |
| `ingest-xbrl` | Ingest XBRL text blocks for a company/period |
| `run-scheduler` | Start APScheduler daemon (monthly syncs) |
| `run-sync` | Manually trigger monthly sync job |

### Key CLI Options

```bash
# Backfill with error handling
uv run opendart backfill --priority-only --on-error-013=mark --on-rate-limit=pause

# Import KOSPI 200 companies and backfill
uv run opendart import-by-stock-code "KOSPI 200.csv" --backfill

# Ingest XBRL notes
uv run opendart ingest-xbrl --corp-code 00126380 --year 2024 --report-code 11011
```

## Key Domain Concepts

| Term | Description |
|------|-------------|
| `corp_code` | DART's 8-digit company identifier (stable, used as PK) |
| `stock_code` | 6-digit KRX ticker (may be reused after delisting) |
| `report_code` | `11013` (Q1), `11012` (Q2), `11014` (Q3), `11011` (Q4/Annual) |
| `fs_div` | Financial statement division - `CFS` (consolidated) or `OFS` (standalone) |
| `rcept_no` | 14-digit receipt number for DART disclosures |
| `earliest_data_year` | Tracked per company to skip wasteful API queries |

**Important**: Always use `corp_code` (not `stock_code`) for database relationships - stock codes can be reused after delisting.

## Database Schema

Five tables with `corp_code` as the linking key:

| Table | Purpose |
|-------|---------|
| `companies` | Master table - identifiers, listing dates, priority flag |
| `financial_fundamentals` | Financial statement line items with versioning |
| `key_events` | Disclosures keyed by `rcept_no` |
| `financial_notes` | XBRL text block notes (NEW) |
| `backfill_progress` | Checkpoint table for resumable backfill |

**View**: `latest_financials` - shows only the most recent version of each financial entry.

### Model Field Sizes

DART returns longer values than expected. Key field sizes in `models.py`:
- `account_id`: 200 chars (e.g., `ifrs-full_NoncontrollingInterestsInSubsidiaries`)
- `account_name`: 255 chars (Korean names)
- `concept_id`: 255 chars (XBRL concept identifiers)

## Alembic Migrations

```bash
# Run all migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision -m "description"
```

Migrations in `alembic/versions/`:
1. `001_initial_schema.py` - Core tables
2. `002_latest_financials_view.py` - Latest_Financials view
3. `1af33ea2791c_create_financial_notes.py` - XBRL notes table

## API Constraints

| Constraint | Value |
|------------|-------|
| Daily limit | 20,000 requests |
| Throttling | 0.15s delay between requests |
| Data availability | `finstate_all()` from 2015 Q1 onwards |

**Error codes**: 010 (unregistered key), 011 (expired), 013 (no data), 020 (rate limit), 800 (data doesn't exist)

## Configuration

Environment variables in `.env` file (see `.env.example`):

```bash
# Required
DART_API_KEY=your-api-key
DATABASE_URL=postgresql://user:pass@host/dbname

# Optional (email notifications)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user
SMTP_PASSWORD=password
NOTIFICATION_EMAIL=alerts@example.com
```

## Development

### Python ETL

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest tests/

# Run CLI
uv run opendart --help
```

### Web Dashboard

```bash
cd web

# Install dependencies
npm install

# Introspect existing database schema
npx prisma db pull
npx prisma generate

# Start dev server
npm run dev           # localhost:3000

# Build for production
npm run build
```

### Vercel Deployment

Set `DATABASE_URL` environment variable. Format for Neon:
```
postgresql://user:password@host/dbname?sslmode=require
```

## Web Dashboard API Routes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/companies` | GET | List companies with search, pagination |
| `/api/companies?search=삼성` | GET | Search by name |
| `/api/financials/[corpCode]` | GET | Get financials for a company |
| `/api/financials/[corpCode]?year=2024&report_code=11011` | GET | Filter by year/quarter |

## Common Pitfalls

### OpenDartReader Import

`OpenDartReader` is a class, not a module:
```python
import OpenDartReader
dart = OpenDartReader(api_key)  # Correct
# NOT: OpenDartReader.OpenDartReader(api_key)
```

### PostgreSQL Socket Connection

When using peer authentication, the OS user must match the DB role:
```bash
DATABASE_URL=postgresql:///opendart_updater  # Uses current OS user
```

If connecting as different user:
```sql
CREATE ROLE your_os_user WITH LOGIN SUPERUSER;
```

### Vercel DATABASE_URL Format

Must start with `postgresql://` or `postgres://` protocol:
```
Error validating datasource `db`: the URL must start with the protocol `postgresql://`
```

### Radix UI Select Empty Values

Radix UI Select does NOT support empty string `""` as a value (causes hydration errors):

```tsx
// Wrong
const [value, setValue] = useState("");
<SelectItem value="">All</SelectItem>

// Correct
const [value, setValue] = useState<string | undefined>(undefined);
<SelectItem value="all">All</SelectItem>

// Check for sentinel in logic
if (value && value !== "all") { /* Apply filter */ }
```

### BigInt JSON Serialization

When returning financial data from API routes, `BigInt` values must be converted:
```typescript
// Prisma returns BigInt for amount field
const data = financials.map(f => ({
  ...f,
  amount: f.amount ? Number(f.amount) : null
}));
```

### XBRL Arelle Dependency

Arelle requires lxml. Install system dependencies on Linux:
```bash
apt-get install libxml2-dev libxslt-dev
```

## Testing

```bash
# Run all tests
uv run pytest tests/

# With coverage
uv run pytest tests/ --cov=src/opendart

# Specific test file
uv run pytest tests/test_companies_ingest.py -v
```

Test files:
- `tests/test_companies_ingest.py` - Company ingestion, stock code reuse
- `tests/test_financials_helpers.py` - `parse_amount()` and transformations

## Architecture Diagram

```
┌─────────────────────────────────────────────┐
│       Next.js Web Dashboard (web/)          │
│      React 19 + Tailwind + Prisma ORM       │
└─────────────────┬───────────────────────────┘
                  │ API Routes
                  ▼
┌─────────────────────────────────────────────┐
│            PostgreSQL Database              │
│  companies | financial_fundamentals | ...   │
└─────────────────┬───────────────────────────┘
                  ▲
     ┌────────────┴────────────┐
     │                         │
     ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│   CLI (cli.py)   │    │   Scheduler      │
│   9 commands     │    │   (APScheduler)  │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌─────────────────────┐
         │    ETL Modules      │
         │ companies.py        │
         │ financials.py       │
         │ events.py           │
         │ xbrl.py             │
         └─────────┬───────────┘
                   ▼
         ┌─────────────────────┐
         │   DartClient        │
         │  (OpenDartReader)   │
         └─────────┬───────────┘
                   ▼
         ┌─────────────────────┐
         │   Open DART API     │
         │  (External Service) │
         └─────────────────────┘
```

## File Naming Conventions

- Python: `snake_case.py`
- TypeScript/React: `kebab-case.tsx` for components, `route.ts` for API routes
- Database columns: `snake_case`
- CLI commands: `kebab-case` (e.g., `import-by-stock-code`)

## Dependencies

### Python (pyproject.toml)
- `opendartreader>=0.2.0` - DART API wrapper
- `sqlalchemy>=2.0` - ORM
- `psycopg2-binary>=2.9` - PostgreSQL driver
- `alembic>=1.13` - Migrations
- `click>=8.0` - CLI framework
- `pandas>=2.0` - Data manipulation
- `apscheduler>=3.10` - Job scheduling
- `arelle-release>=2.0` - XBRL parsing
- `lxml>=4.9` - XML processing

### Node.js (web/package.json)
- `next@16.1.4` - React framework
- `react@19.2.3` - UI library
- `@prisma/client@^5.22.0` - Database ORM
- `tailwindcss@^4` - CSS framework
- `@radix-ui/react-*` - UI primitives
