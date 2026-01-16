"""ETL module for financial fundamentals data."""

import logging
from datetime import datetime
from typing import Generator

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from opendart.api import DartClient, DartError, DartErrorCode
from opendart.models import BackfillProgress, Company, FinancialFundamental

logger = logging.getLogger(__name__)

# Report codes mapping
REPORT_CODES = {
    "11013": "Q1",
    "11012": "Q2",
    "11014": "Q3",
    "11011": "Q4/Annual",
}


def parse_amount(value: str | int | float | None) -> int | None:
    """Parse amount value from DART response.

    Handles comma-separated strings, negative values, etc.
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return int(value)

    # Handle string values
    value_str = str(value).strip()
    if not value_str or value_str == "-":
        return None

    # Remove commas and parse
    try:
        return int(value_str.replace(",", ""))
    except ValueError:
        logger.warning(f"Could not parse amount value: {value}")
        return None


def transform_financial_data(
    df: pd.DataFrame,
    corp_code: str,
    year: int,
    report_code: str,
) -> list[dict]:
    """Transform DART financial data to model format.

    Args:
        df: DataFrame from finstate_all()
        corp_code: Company code
        year: Reporting year
        report_code: Report code

    Returns:
        List of dicts ready for insertion
    """
    if df.empty:
        return []

    records = []
    now = datetime.utcnow()

    for _, row in df.iterrows():
        # Get financial statement division (CFS or OFS)
        fs_div = row.get("fs_div", "OFS")

        # Get account info
        account_id = row.get("account_id", row.get("sj_div", ""))
        account_name = row.get("account_nm", row.get("account_detail", ""))

        # Get amount - try different column names
        amount = None
        for col in ["thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount", "amount"]:
            if col in row and pd.notna(row[col]):
                amount = parse_amount(row[col])
                break

        records.append(
            {
                "corp_code": corp_code,
                "year": year,
                "report_code": report_code,
                "fs_div": fs_div,
                "account_id": str(account_id) if account_id else "",
                "account_name": str(account_name) if account_name else "",
                "amount": amount,
                "version": 1,
                "fetched_at": now,
            }
        )

    return records


def fetch_company_financials(
    client: DartClient,
    session: Session,
    corp_code: str,
    year: int,
    report_code: str,
    on_error_013: str = "skip",  # 'skip', 'mark', 'stop'
) -> tuple[int, str]:
    """Fetch and store financial data for a single company/year/report.

    Args:
        client: DART API client
        session: Database session
        corp_code: Company code
        year: Reporting year
        report_code: Report code
        on_error_013: How to handle "no data" errors

    Returns:
        Tuple of (records_inserted, status)
    """
    try:
        df = client.finstate_all(corp_code, year, report_code)

        if df.empty:
            logger.info(f"No data for {corp_code} {year} {report_code}")
            return 0, "no_data"

        records = transform_financial_data(df, corp_code, year, report_code)

        if not records:
            return 0, "no_records"

        # Use PostgreSQL upsert (ON CONFLICT DO NOTHING for duplicates)
        stmt = insert(FinancialFundamental).values(records)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                "corp_code",
                "year",
                "report_code",
                "fs_div",
                "account_id",
                "version",
            ]
        )

        result = session.execute(stmt)
        session.commit()

        inserted = result.rowcount if result.rowcount else len(records)
        logger.info(f"Inserted {inserted} records for {corp_code} {year} {report_code}")

        return inserted, "success"

    except DartError as e:
        if e.code == DartErrorCode.NO_DATA.value:
            logger.info(f"No data available for {corp_code} {year} {report_code}")
            if on_error_013 == "skip":
                return 0, "skipped"
            elif on_error_013 == "stop":
                return 0, "stopped"
            else:
                return 0, "skipped"

        elif e.code == DartErrorCode.RATE_LIMIT.value:
            logger.warning(f"Rate limit hit for {corp_code} {year} {report_code}")
            return 0, "rate_limited"

        else:
            logger.error(f"DART error for {corp_code} {year} {report_code}: {e}")
            return 0, f"error_{e.code}"

    except Exception as e:
        logger.error(f"Unexpected error for {corp_code} {year} {report_code}: {e}")
        session.rollback()
        return 0, "error"


def get_years_to_backfill(start_year: int = 2015) -> list[int]:
    """Get list of years to backfill from start_year to current year."""
    current_year = datetime.now().year
    return list(range(start_year, current_year + 1))


def get_report_codes() -> list[str]:
    """Get list of report codes to fetch."""
    return list(REPORT_CODES.keys())


def backfill_company(
    client: DartClient,
    session: Session,
    corp_code: str,
    start_year: int = 2015,
    on_error_013: str = "skip",
) -> dict:
    """Backfill all financial data for a company.

    Args:
        client: DART API client
        session: Database session
        corp_code: Company code
        start_year: Year to start backfill from
        on_error_013: How to handle "no data" errors

    Returns:
        Dictionary with stats (total_records, errors, etc.)
    """
    stats = {
        "total_records": 0,
        "successful": 0,
        "skipped": 0,
        "errors": 0,
        "rate_limited": False,
    }

    years = get_years_to_backfill(start_year)
    report_codes = get_report_codes()

    for year in years:
        for report_code in report_codes:
            # Check if already processed
            existing = session.execute(
                select(BackfillProgress).where(
                    BackfillProgress.corp_code == corp_code,
                    BackfillProgress.year == year,
                    BackfillProgress.report_code == report_code,
                    BackfillProgress.status == "completed",
                )
            ).scalar_one_or_none()

            if existing:
                logger.debug(f"Skipping already processed {corp_code} {year} {report_code}")
                continue

            records, status = fetch_company_financials(
                client, session, corp_code, year, report_code, on_error_013
            )

            stats["total_records"] += records

            if status == "success":
                stats["successful"] += 1
            elif status in ("skipped", "no_data", "no_records"):
                stats["skipped"] += 1
            elif status == "rate_limited":
                stats["rate_limited"] = True
                # Record progress and stop
                _record_progress(session, corp_code, year, report_code, "rate_limited")
                return stats
            else:
                stats["errors"] += 1
                _record_progress(session, corp_code, year, report_code, "failed", status)
                continue

            # Record successful progress
            _record_progress(session, corp_code, year, report_code, "completed")

    return stats


def _record_progress(
    session: Session,
    corp_code: str,
    year: int,
    report_code: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Record backfill progress."""
    stmt = insert(BackfillProgress).values(
        corp_code=corp_code,
        year=year,
        report_code=report_code,
        status=status,
        error_message=error_message,
        processed_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["corp_code", "year", "report_code"],
        set_={
            "status": status,
            "error_message": error_message,
            "processed_at": datetime.utcnow(),
        },
    )
    session.execute(stmt)
    session.commit()


def get_companies_for_backfill(
    session: Session, priority_only: bool = False
) -> Generator[Company, None, None]:
    """Get companies to backfill.

    Args:
        session: Database session
        priority_only: If True, only return priority companies

    Yields:
        Company objects
    """
    query = select(Company)

    if priority_only:
        query = query.where(Company.is_priority == True)

    # Process priority companies first
    query = query.order_by(Company.is_priority.desc(), Company.corp_code)

    result = session.execute(query)
    for row in result.scalars():
        yield row
