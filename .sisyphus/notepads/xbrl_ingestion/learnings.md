# Learnings: XBRL Notes Ingestion

## Conventions
- Follow existing ETL pattern: return stats dict `{"total_records": N, "errors": N, ...}`
- Use PostgreSQL upserts via `on_conflict_do_update`
- Session management: `with get_session() as session:`
- Rate limiting: All API calls through `DartClient._wait_for_rate_limit()`

## Patterns from Codebase
- Domain naming preserved: `corp_code`, `stock_code`, `report_code`, `fs_div`
- Error handling: `DartErrorCode.NO_DATA` (013), `DartErrorCode.RATE_LIMIT` (020)
- Temp file cleanup: Use `tempfile.TemporaryDirectory()` context manager

## XBRL-Specific
- Text blocks identified by: `fact.concept.type.name` contains `"textBlock"`
- XBRL download requires `rcept_no` (receipt number), not just `corp_code`
- Must lookup `rcept_no` via `client.list()` API first

## Dependencies Setup (Wave 1)
- `arelle-release>=2.0` is the official Arelle package for XBRL parsing
- `lxml>=4.9` is required by Arelle for XML processing
- Both are runtime dependencies (added to main `dependencies` array, not dev)
- Installation via `uv sync` resolves all transitive dependencies automatically
- Arelle v2.38.7 installed with dependencies: pillow, openpyxl, jsonschema, regex, etc.
- Verification: `import arelle` and `import lxml` both work after sync

## Task 2: Create financial_notes Table Schema (Jan 28, 2026)

### What Was Done
- Added `FinancialNote` model to `src/opendart/models.py` following existing `FinancialFundamental` pattern
- Added `Text` import to SQLAlchemy imports for content field
- Added `financial_notes` relationship to `Company` model with `back_populates`
- Generated Alembic migration: `1af33ea2791c_create_financial_notes.py`
- Applied migration successfully to database

### Schema Details
Table: `financial_notes`
- `id`: Integer PK, autoincrement
- `corp_code`: String(8), FK to companies.corp_code, indexed
- `rcept_no`: String(14), indexed - Receipt number for XBRL lineage
- `year`: Integer
- `report_code`: String(5)
- `concept_id`: String(255) - XBRL concept identifier
- `title`: String(500) - Human-readable label
- `content`: Text - The actual text/HTML content
- `context_ref`: String(100) - XBRL context reference
- `fetched_at`: DateTime, default=datetime.utcnow
- UniqueConstraint on (`corp_code`, `rcept_no`, `concept_id`)

### Key Patterns Followed
1. **Model Structure**: Followed `FinancialFundamental` pattern with autoincrement PK + composite unique constraint
2. **Relationships**: Used `back_populates` for bidirectional relationship with Company
3. **Indexes**: Added indexes on `corp_code` (FK) and `rcept_no` (for XBRL lineage queries)
4. **DateTime**: Used `default=datetime.utcnow` for timestamp field
5. **Migration**: Used `--autogenerate` to detect schema changes automatically

### Technical Notes
- Had to set `PYTHONPATH` to include `src/` directory for Alembic to find `opendart` module
- Migration command: `export PYTHONPATH=.../src:$PYTHONPATH && .venv/bin/alembic revision --autogenerate -m "create_financial_notes"`
- Alembic detected table creation, indexes, and FK constraint automatically
- Migration also updated `companies.earliest_data_year` comment (minor change)

### Verification
- Confirmed table exists in database with all 10 columns
- Confirmed indexes created: `ix_financial_notes_corp_code`, `ix_financial_notes_rcept_no`
- Confirmed unique constraint: `unique_financial_note` on (corp_code, rcept_no, concept_id)
- Confirmed FK constraint to `companies.corp_code`

### Next Steps
- Task 3 will implement the ETL logic to fetch and parse XBRL data into this table

## Task 3: Add download_xbrl Method to DartClient (Jan 28, 2026)

### What Was Done
- Added `download_xbrl(self, rcept_no: str, save_path: str) -> str` method to `DartClient` class in `src/opendart/api.py`
- Method wraps `self._dart.finstate_xml(rcept_no, save_as=save_path)` API call
- Follows same error handling pattern as `finstate_all` method

### Implementation Details
1. **Rate Limiting**: Calls `self._wait_for_rate_limit()` before API request
2. **API Call**: Wraps `self._dart.finstate_xml(rcept_no, save_as=save_path)`
3. **Error Handling**:
   - Checks if result is None → raises `DartError` with `NO_DATA` code
   - Calls `self._check_error(result, context)` for API error responses
   - Catches and re-raises `DartError` exceptions
   - Catches unexpected exceptions and logs them
4. **Return Value**: Returns the `save_path` string (path to downloaded file)
5. **Logging**: Uses context string `f"download_xbrl({rcept_no})"` for all log messages

### Code Pattern Followed
```python
def download_xbrl(self, rcept_no: str, save_path: str) -> str:
    self._wait_for_rate_limit()
    context = f"download_xbrl({rcept_no})"
    
    try:
        logger.debug(f"Calling {context}")
        result = self._dart.finstate_xml(rcept_no, save_as=save_path)
        
        if result is None:
            logger.warning(f"No data returned for {context}")
            raise DartError(
                code=DartErrorCode.NO_DATA.value,
                message=f"No XBRL data available for {rcept_no}",
            )
        
        self._check_error(result, context)
        logger.debug(f"Successfully downloaded XBRL to {save_path}")
        return save_path
    
    except DartError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in {context}: {e}")
        raise
```

### Verification
- Python syntax verified with `python3 -m py_compile`
- Method added at lines 229-264 in `src/opendart/api.py`
- Follows existing conventions: type hints, docstring, error handling pattern
- Ready for use in ETL flows to download XBRL files for financial note extraction

## Task 4: Implement XBRL Ingestion Module (Jan 28, 2026)

### What Was Done
- Added `src/opendart/etl/xbrl.py` with `ingest_xbrl(corp_code, year, report_code)`
- Lookup `rcept_no` via `client.list(..., kind="A")` and filter on `reprt_code`/`report_code`
- Download XBRL ZIP to `tempfile.TemporaryDirectory()`, extract, and select instance `.xml` excluding `_cal/_def/_pre/_lab`
- Parse with Arelle `Cntlr(logFileName="logToStdErr")` and `modelManager.load(...)`, then `modelManager.close(...)`
- Extract text blocks where `concept.type.name` contains `textBlock` and upsert into `financial_notes`

### Parsing Notes
- Multiple facts can share the same `concept_id`; dedupe by `concept_id` to satisfy the unique constraint
- Text blocks may be empty; handle gracefully and return zero counts

### Diagnostics
- Added local stubs in `typings/arelle/__init__.pyi` so basedpyright can type-check Arelle usage

## Task 5: Add ingest-xbrl CLI Command (Jan 28, 2026)

### What Was Done
- Added `ingest_xbrl` command to `src/opendart/cli.py`
- Imported `ingest_xbrl` function from `opendart.etl.xbrl`
- Created `@cli.command("ingest-xbrl")` with three Click options:
  - `--corp-code` (required, type=str): DART 8-digit company identifier
  - `--year` (required, type=int): Year to ingest XBRL data for
  - `--report-code` (optional, default="11011", type=str): Report code (11011=Annual, 11013=Q1, 11012=Q2, 11014=Q3)

### Implementation Details
1. **Function Signature**: `ingest_xbrl_command(corp_code: str, year: int, report_code: str) -> None`
2. **Docstring**: Includes description and two usage examples
3. **Execution**: Calls `ingest_xbrl(corp_code, year, report_code)` and prints stats via `_print_stats()`
4. **Stats Output**: Uses existing `_print_stats()` helper with heading "XBRL ingestion summary"

### Code Pattern Followed
```python
@cli.command("ingest-xbrl")
@click.option("--corp-code", required=True, type=str, help="DART corp_code (8-digit identifier).")
@click.option("--year", required=True, type=int, help="Year to ingest XBRL data for.")
@click.option(
    "--report-code",
    default="11011",
    show_default=True,
    type=str,
    help="Report code (11011=Annual, 11013=Q1, 11012=Q2, 11014=Q3).",
)
def ingest_xbrl_command(corp_code: str, year: int, report_code: str) -> None:
    """Ingest XBRL text blocks for a company/report period.
    
    Fetches XBRL disclosure documents from DART API and stores text blocks
    in the database for the specified company, year, and report period.
    
    Example:
        opendart ingest-xbrl --corp-code 00126380 --year 2024
        opendart ingest-xbrl --corp-code 00126380 --year 2024 --report-code 11013
    """
    stats = ingest_xbrl(corp_code, year, report_code)
    _print_stats(stats, heading="XBRL ingestion summary")
```

### Verification
- Command help works: `opendart ingest-xbrl --help` displays all options and examples
- Follows existing CLI patterns from `sync_events_command`, `backfill_command`, etc.
- Uses `_print_stats()` helper for consistent output formatting
- All required parameters are marked with `required=True`
- Default report_code matches DART convention (11011 = Annual)

### Integration
- Command is now available as: `opendart ingest-xbrl --corp-code <code> --year <year> [--report-code <code>]`
- Integrates with existing ETL pipeline (Tasks 1-4)
- Ready for production use in monthly sync jobs or manual invocation
