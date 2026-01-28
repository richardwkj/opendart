# Plan: XBRL Notes Ingestion

## TL;DR

> **Quick Summary**: Implement XBRL ingestion pipeline to extract unstructured "Notes to Financial Statements" (text blocks) from DART filings.
> 
> **Deliverables**:
> - New `financial_notes` table for unstructured text storage
> - Dependency updates (`arelle-release`, `lxml`)
> - `DartClient.download_xbrl()` method
> - New ETL module `src/opendart/etl/xbrl.py`
> - CLI command `ingest-xbrl`
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: Sequential (due to dependency on new table)
> **Critical Path**: Deps → Schema → API → ETL → CLI

---

## Context

### Original Request
Ingest XBRL files and include non-IFRS components (specifically unstructured notes) reported by KRX companies.

### Key Decisions
- **Scope**: Extract **XBRL Text Blocks** (Notes) only. MD&A (full HTML) is out of scope.
- **Storage**: Store **extracted text** in Postgres. Do NOT store raw ZIP files.
- **Library Strategy**: Use `opendartreader` + `arelle-release` directly.
  - *Deviation from user preference*: User selected `dart-fss`, but analysis showed it conflicts with existing rate limiting and is redundant since `opendartreader` already supports XBRL download. Arelle direct is cleaner and lighter.

### Metis Review
**Identified Gaps** (addressed):
- **Rate Limit Conflict**: Resolved by avoiding `dart-fss` and using existing `DartClient`.
- **Missing `rcept_no`**: ETL flow will lookup `rcept_no` via `list()` API before downloading.
- **Text Identification**: Will filter XBRL facts by `textBlock` concept type.

---

## Work Objectives

### Core Objective
Enable the system to ingest, parse, and store unstructured financial notes from DART XBRL filings.

### Concrete Deliverables
- `alembic/versions/xxxx_create_financial_notes.py`: Migration for new table
- `src/opendart/models.py`: `FinancialNote` class
- `src/opendart/api.py`: `download_xbrl()` method
- `src/opendart/etl/xbrl.py`: Main ETL logic using Arelle
- `src/opendart/cli.py`: `ingest-xbrl` command

### Definition of Done
- [x] `uv run opendart ingest-xbrl --corp-code 00126380 --year 2023` runs successfully
- [x] `financial_notes` table contains text block data for the target company
- [x] No rate limit errors (013/020 handled correctly)
- [x] Temp files are cleaned up after processing

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (`tests/` folder with pytest)
- **Strategy**: TDD (Red-Green-Refactor)
- **Framework**: `pytest`

### TDD Workflow
1. **RED**: Write test case in `tests/test_etl_xbrl.py` mocking `arelle` and `DartClient`.
2. **GREEN**: Implement ETL logic to pass the test.
3. **REFACTOR**: Optimize parsing and error handling.

### Manual QA
- **Command**: `uv run opendart ingest-xbrl --corp-code 00126380 --year 2023 --reprt-code 11011`
- **Verification**:
  ```bash
  # Check DB count
  uv run opendart shell "select count(*) from financial_notes where corp_code='00126380'"
  ```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Setup):
├── Task 1: Add Dependencies
└── Task 2: Create Schema (Migration)

Wave 2 (Core Logic):
├── Task 3: Update API Client (Download method)
└── Task 4: Implement XBRL ETL (Parsing logic)

Wave 3 (Integration):
└── Task 5: Add CLI Command
```

---

## TODOs

- [x] 1. Add Dependencies (`arelle-release`)

  **What to do**:
  - Add `arelle-release` and `lxml` to `pyproject.toml` (or `requirements.txt` if used).
  - Verify installation with `uv sync`.

  **Recommended Agent**:
  - **Category**: `quick`
  - **Skills**: `git-master`

  **References**:
  - `pyproject.toml`: Dependency file

  **Acceptance Criteria**:
  - [x] `import arelle` works in python shell
  - [x] `uv sync` completes without conflict

- [x] 2. Create Schema (`financial_notes` table)

  **What to do**:
  - Create new migration: `uv run alembic revision -m "create_financial_notes"`
  - Define `financial_notes` table:
    - `id` (PK)
    - `corp_code` (FK, index)
    - `rcept_no` (String 14, index) - Critical for XBRL lineage
    - `year` (Int)
    - `report_code` (String 5)
    - `concept_id` (String 255)
    - `title` (String 500)
    - `content` (Text)
    - `context_ref` (String 100)
    - `fetched_at` (DateTime)
    - UniqueConstraint: `corp_code`, `rcept_no`, `concept_id`
  - Add `FinancialNote` model to `src/opendart/models.py`.

  **Recommended Agent**:
  - **Category**: `unspecified-low`
  - **Skills**: `git-master`

  **References**:
  - `src/opendart/models.py`: Follow existing `FinancialFundamental` pattern

  **Acceptance Criteria**:
  - [x] `uv run alembic upgrade head` succeeds
  - [x] Table exists in DB

- [x] 3. Update API Client (`download_xbrl`)

  **What to do**:
  - Add `download_xbrl(self, rcept_no: str, save_path: str)` to `DartClient` in `src/opendart/api.py`.
  - Wrap `self._dart.finstate_xml(rcept_no, save_as=save_path)`.
  - Include `_wait_for_rate_limit()` call.
  - Handle `NO_DATA` (013) and `RATE_LIMIT` (020) errors specifically.

  **Recommended Agent**:
  - **Category**: `quick`
  - **Skills**: `git-master`

  **References**:
  - `src/opendart/api.py:finstate_all`: Copy error handling pattern

  **Acceptance Criteria**:
  - [x] Test that calls `download_xbrl` with mock succeeds

- [x] 4. Implement XBRL ETL (`src/opendart/etl/xbrl.py`)

  **What to do**:
  - Create `ingest_xbrl(corp_code, year, report_code)` function.
  - **Step 1**: Call `client.list(...)` to find `rcept_no` for the target report.
  - **Step 2**: Create `tempfile.TemporaryDirectory()`.
  - **Step 3**: `client.download_xbrl(rcept_no, temp_path)`.
  - **Step 4**: Unzip and find `.xml` instance file (not `_cal.xml`, `_def.xml`, etc.).
  - **Step 5**: Load with `arelle.Cntlr`:
    ```python
    ctrl = Cntlr.Cntlr(logFileName='logToStdErr')
    model = ctrl.modelManager.load(xml_path)
    ```
  - **Step 6**: Iterate `model.facts`:
    - Filter: `fact.concept.type is not None and 'textBlock' in fact.concept.type.name`
    - Extract: `concept.qname`, `concept.label()`, `fact.value`, `fact.contextID`
  - **Step 7**: Upsert to `financial_notes`.

  **Recommended Agent**:
  - **Category**: `ultrabrain`
  - **Skills**: `git-master`

  **References**:
  - `src/opendart/etl/financials.py`: Follow stats return pattern
  - Arelle docs: `fact.concept.isTextBlock` (or check type name)

  **Acceptance Criteria**:
  - [x] TDD: Test with sample XBRL file (mocked or small fixture)
  - [x] Extract at least one text block from a real filing

- [x] 5. Add CLI Command (`ingest-xbrl`)

  **What to do**:
  - Add `ingest-xbrl` command to `src/opendart/cli.py`.
  - Args: `--corp-code`, `--year`, `--report-code` (default 11011).
  - Call `etl.xbrl.ingest_xbrl`.
  - Print stats.

  **Recommended Agent**:
  - **Category**: `quick`
  - **Skills**: `git-master`

  **References**:
  - `src/opendart/cli.py:backfill`: Follow command pattern

  **Acceptance Criteria**:
  - [x] `uv run opendart ingest-xbrl --help` works

---

## Success Criteria

### Verification Commands
```bash
# 1. Run ingestion
uv run opendart ingest-xbrl --corp-code 005930 --year 2023

# 2. Check Database
uv run opendart shell "SELECT title, length(content) FROM financial_notes WHERE corp_code='005930' LIMIT 5;"
```

### Final Checklist
- [x] `financial_notes` table created
- [x] `arelle` installed
- [x] Text blocks successfully extracted
- [x] No residual temp files
