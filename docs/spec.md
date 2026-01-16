## Korean Financial Data Automator – Specification

### 1. Product Overview

An automated Python-based ETL (Extract, Transform, Load) system designed to pull financial fundamentals and key corporate events for listed Korean companies using the `OpenDartReader` library and store them in a relational database.

- **Goal**: Maintain an up-to-date, queryable dataset of Korean listed companies’ fundamentals and key corporate events.
- **Scope**: Publicly listed Korean companies covered by the Open DART API.

### 2. Core Technologies

- **Language**: Python 3.10+
- **Data Source**: Open DART API via the `OpenDartReader` library
- **Database**: Relational database (PostgreSQL recommended; MySQL or SQLite also supported)
- **Automation / Scheduling**:
  - Internal: APScheduler
  - External: Cron, GitHub Actions, or similar schedulers
- **Configuration**:
  - API keys and database credentials are stored in a `.env` file (excluded from version control via `.gitignore`).

### 3. Data Collection Logic

The system will interface with `OpenDartReader` to fetch two primary datasets: **Financial Fundamentals** and **Key Events Data**.

#### 3.1 Financial Fundamentals

- **Source Function**: `dart.finstate_all()`
- **Scope**:
  - Balance Sheet
  - Income Statement
  - Cash Flow Statement
- **Frequency**:
  - Quarterly reports (e.g., report codes: `11013`, `11012`, `11011`)
- **Data Validation & Cleaning**:
  - Ensure numeric values are stored as numbers.
  - Convert DART string outputs containing commas (e.g., `"1,234,567"`) into integers or appropriate numeric types.

#### 3.2 Key Events Data

- **Source Functions**:
  - `dart.list()`
  - `dart.event()`
  - `dart.report()` (for stock/dividend-related disclosures)
- **Scope**:
  - **Major Issues (Kind B)**:
    - Mergers and acquisitions
    - Asset disposals
    - Defaults and other major credit events
  - **Stock / Dividend Events**:
    - Cash and stock dividends
    - Stock splits / reverse splits
    - Capital increases (paid-in capital, rights issues, etc.)

### 4. Database Schema Design

To ensure stable company identification, the system will use `corp_code` (DART's 8-digit company code) as the **Primary Key (PK)** in a **Master–Detail** architecture.

> **Note**: `corp_code` is more stable than `stock_code` because stock codes can be reused after delisting. Financial data is time-series (multiple reports per company). Therefore, `corp_code` serves as a primary key in the master table and as a foreign key (FK) in detail tables.

#### 4.1 Table: `Companies` (Master)

- **Purpose**: Store the canonical list of companies and core identifiers.

| Column        | Type         | Constraint        | Description                               |
|--------------|--------------|-------------------|-------------------------------------------|
| `corp_code`  | VARCHAR(8)   | PRIMARY KEY       | DART-specific 8-digit company code (stable identifier) |
| `stock_code` | VARCHAR(6)   | UNIQUE            | 6-digit KRX ticker (may be reused after delisting) |
| `corp_name`  | VARCHAR(255) |                   | Legal name of company                     |
| `is_priority`| BOOLEAN      | DEFAULT FALSE     | Flag for user-designated priority company |
| `listing_date` | DATE       |                   | Date of IPO/listing                       |
| `delisted_date` | DATE      |                   | Date of delisting (NULL if still listed)  |
| `last_updated` | TIMESTAMP  |                   | Timestamp of last successful sync         |

- **New Company Ingestion**:
  - New IPO companies will be added via a **CSV file** uploaded by the user.
  - The system must validate uploads against the existing `Companies` table to detect and reject duplicates (matching on `corp_code`).
- **Delisting Updates**:
  - Delisting events are detected by the user and uploaded. The `delisted_date` column will be populated via user-provided updates.
- **Stock Code Reuse Handling**:
  - When a stock code is reused by a new company after a previous company delisted, the system will offer the user options:
    1. Update the old company's `stock_code` to NULL and assign the code to the new company.
    2. Reject the new company upload and alert the user to resolve manually.

#### 4.2 Table: `Financial_Fundamentals` (Detail)

- **Purpose**: Store normalized financial statement line items per company, year, and report. Supports versioning for restated financials.

| Column        | Type         | Constraint          | Description                                   |
|--------------|--------------|---------------------|-----------------------------------------------|
| `id`         | SERIAL       | PRIMARY KEY         | Internal surrogate key                        |
| `corp_code`  | VARCHAR(8)   | FOREIGN KEY         | References `Companies(corp_code)`             |
| `year`       | INT          |                     | Reporting year (e.g., 2024)                   |
| `report_code`| VARCHAR(5)   |                     | Report code (e.g., `11011` annual, `11013` Q1)|
| `fs_div`     | VARCHAR(3)   |                     | Financial statement division: `CFS` (consolidated) or `OFS` (standalone) |
| `account_id` | VARCHAR(20)  |                     | DART account identifier code                  |
| `account_name` | VARCHAR(100)|                    | e.g., `"Revenue"`, `"Net Income"`             |
| `amount`     | BIGINT       |                     | Value in KRW                                  |
| `version`    | INT          | DEFAULT 1           | Version number for restated financials        |
| `fetched_at` | TIMESTAMP    |                     | Timestamp when this record was fetched        |

##### 4.2.1 Uniqueness & De-duplication Strategy (Compute-Efficient)

To prevent duplicate financial entries and minimize application-side computation, the system will use a **database-level composite unique constraint** on the natural key of the `Financial_Fundamentals` table.

- **Chosen Strategy (Recommended – Most Compute-Efficient)**:
  - Define a composite unique constraint on:
    - `corp_code`, `year`, `report_code`, `fs_div`, `account_id`, `version`
  - Example DDL:

    ```sql
    ALTER TABLE Financial_Fundamentals
    ADD CONSTRAINT unique_financial_entry
    UNIQUE (corp_code, year, report_code, fs_div, account_id, version);
    ```

- **Rationale**:
  - Offloads de-duplication to the database engine (highly optimized and index-backed).
  - Guarantees data integrity even under concurrent writers.
  - Minimizes Python-side logic and avoids large pre-filtering in Pandas.
  - Including `version` allows storing restated financials without losing historical data.

- **Error Handling Requirement**:
  - The ETL code must catch integrity/unique-violation errors to:
    - Avoid crashing the process.
    - Optionally log and skip duplicates, or switch to an UPSERT for that specific record.

> **Note**: Application-side filtering (e.g., Pandas pre-checks) and pure UPSERT patterns remain possible extensions, but the default and primary mechanism for avoiding duplicates is the composite unique constraint above.

##### 4.2.2 View: `Latest_Financials`

- **Purpose**: Provide a convenient view showing only the latest version of each financial statement entry.

| Column        | Description                                   |
|--------------|-----------------------------------------------|
| `year`       | Reporting year                                |
| `quarter`    | Quarter derived from `report_code` (Q1, Q2, Q3, Q4/Annual) |
| `corp_code`  | DART company code                             |
| `stock_code` | KRX ticker (joined from `Companies`)          |
| `fs_div`     | `CFS` or `OFS`                                |
| `account_name` | Account name                                |
| `account_id` | DART account identifier                       |
| `amount`     | Value in KRW                                  |

- **Example DDL**:

    ```sql
    CREATE VIEW Latest_Financials AS
    SELECT
        f.year,
        CASE f.report_code
            WHEN '11013' THEN 'Q1'
            WHEN '11012' THEN 'Q2'
            WHEN '11014' THEN 'Q3'
            WHEN '11011' THEN 'Q4/Annual'
        END AS quarter,
        f.corp_code,
        c.stock_code,
        f.fs_div,
        f.account_name,
        f.account_id,
        f.amount
    FROM Financial_Fundamentals f
    JOIN Companies c ON f.corp_code = c.corp_code
    WHERE f.version = (
        SELECT MAX(f2.version)
        FROM Financial_Fundamentals f2
        WHERE f2.corp_code = f.corp_code
          AND f2.year = f.year
          AND f2.report_code = f.report_code
          AND f2.fs_div = f.fs_div
          AND f2.account_id = f.account_id
    );
    ```

#### 4.3 Table: `Key_Events` (Detail)

- **Purpose**: Store key disclosure events and filings per company.

| Column        | Type        | Constraint          | Description                                 |
|--------------|-------------|---------------------|---------------------------------------------|
| `rcept_no`   | VARCHAR(14) | PRIMARY KEY         | Unique DART receipt number                  |
| `corp_code`  | VARCHAR(8)  | FOREIGN KEY         | References `Companies(corp_code)`           |
| `report_nm`  | VARCHAR(255)|                     | Title of the disclosure                     |
| `event_date` | DATE        |                     | Date of filing / event                      |

### 5. Execution & Rate Limiting Strategy

Open DART limits standard API keys to **20,000 requests per day**. The system must enforce a conservative rate-limiting strategy.

#### 5.1 Priority Queue

- **Logic**:
  - Query `Companies` for all rows where `is_priority = TRUE`.
  - Process priority companies first before non-priority companies.

#### 5.2 Adaptive Delays & Error Handling

- **Request Throttling**:
  - Implement `time.sleep(0.15)` between requests to stay safely under the daily request threshold and to be resilient to short-term spikes.
- **Rate Limit Handling**:
  - Use `try`–`except` blocks to capture **Error Code 020 (Rate limit exceeded)** from Open DART.
  - On encountering Error Code 020, the system will offer the user two options:
    1. Pause the process for **1 hour** and then resume automatically.
    2. Exit the program gracefully and log current progress (e.g., last processed company and time).
- **Error Logging**:
  - All DART API errors must be logged with timestamp, error code, and context. Relevant error codes include:
    - 010: Unregistered API key
    - 011: Expired API key
    - 013: No data for this query
    - 020: Rate limit exceeded
    - 800: Requested data does not exist
- **Error 013 Handling** (No data for this query):
  - During backfill, many companies may not have data for older years. On encountering Error 013, the system will offer options:
    1. Skip and log the error, continue to next company/period.
    2. Mark the company with an `earliest_data_year` field to avoid future wasteful queries.
    3. Stop processing this company and move to the next.
- **Failure Notification**:
  - On job failure or critical errors, send an email notification to the user's inbox.

#### 5.3 Batching

- **Batch Fetching**:
  - Use `dart.finstate_all()` where possible to pull multiple accounts in a single API call, reducing total requests and improving efficiency.

### 6. Automation (Monthly Schedule)

The script will be deployed as a containerized job or a scheduled task.

#### 6.1 Initial Backfill Strategy

- **Historical Data Range**: Financial data will be backfilled starting from **2015 Q1** (the earliest availability of `dart.finstate_all()`).
- **Execution**: Backfill batches will run on designated (priority) companies first before processing non-priority companies.
- **Progress Tracking & Resumption**:
  - Backfill can span multiple days due to API rate limits. The system will offer options for tracking progress:
    1. **Checkpoint table**: Store last successfully processed `(corp_code, year, report_code)` in a `Backfill_Progress` table. On restart, resume from the last checkpoint.
    2. **File-based checkpoint**: Write progress to a JSON file after each company completes. On restart, read the file to determine where to resume.
    3. **Database flag**: Add a `backfill_completed` boolean to `Companies` table. Mark TRUE after a company's full history is fetched.

#### 6.2 Schedule

- **Frequency**: Monthly
- **Time**: Every **1st of the month at 02:00 KST**
- **Trigger**: Scheduler (APScheduler, Cron, or GitHub Actions workflow)

#### 6.3 Execution Logic

- **Step 1 – Company Sync Check**:
  - For each company in `Companies`, compare the `last_updated` timestamp with the current run time.
- **Step 2 – Update Window**:
  - Fetch disclosures and financial data from the past **31 days** to:
    - Capture new quarterly/annual filings.
    - Capture newly posted key events (major issues, dividends, stock splits, etc.).
- **Step 3 – Persistence & Logging**:
  - Upsert new or updated records into:
    - `Financial_Fundamentals`
    - `Key_Events`
  - Update `Companies.last_updated` on successful completion per company.
  - Log:
    - Number of API calls made
    - Number of companies processed
    - Any rate-limiting pauses or errors encountered

