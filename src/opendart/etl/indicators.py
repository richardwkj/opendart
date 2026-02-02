"""ETL module for financial indicators data (다중회사 주요 재무지표)."""

import logging
from datetime import datetime
from typing import Generator

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from opendart.api import DartClient, DartError, DartErrorCode
from opendart.models import Company, FinancialIndicator, IndicatorBackfillProgress

logger = logging.getLogger(__name__)

# Report codes mapping
REPORT_CODES = {
    "11013": "Q1",
    "11012": "Q2",
    "11014": "Q3",
    "11011": "Q4/Annual",
}

# Indicator category codes
INDICATOR_CATEGORIES = {
    "M210000": "수익성지표",  # Profitability
    "M220000": "안정성지표",  # Stability
    "M230000": "성장성지표",  # Growth
    "M240000": "활동성지표",  # Activity
}

# API data available from 2023 Q3 onwards
EARLIEST_YEAR = 2023
EARLIEST_REPORT_CODE = "11014"  # Q3


def parse_settlement_date(value: str | None) -> datetime | None:
    """Parse settlement date from DART response (YYYY-MM-DD format)."""
    if not value or pd.isna(value):
        return None

    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        logger.warning(f"Could not parse settlement date: {value}")
        return None


def transform_indicator_data(
    df: pd.DataFrame,
    year: int,
    report_code: str,
) -> list[dict]:
    """Transform DART indicator data to model format.

    Args:
        df: DataFrame from fnltt_cmpny_indx()
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
        records.append(
            {
                "corp_code": row.get("corp_code", ""),
                "stock_code": row.get("stock_code"),
                "year": year,
                "report_code": report_code,
                "settlement_date": parse_settlement_date(row.get("stlm_dt")),
                "idx_cl_code": row.get("idx_cl_code", ""),
                "idx_cl_name": row.get("idx_cl_nm", ""),
                "idx_code": row.get("idx_code", ""),
                "idx_name": row.get("idx_nm", ""),
                "idx_value": row.get("idx_val"),
                "fetched_at": now,
            }
        )

    return records


def fetch_indicators_batch(
    client: DartClient,
    session: Session,
    corp_codes: list[str],
    year: int,
    report_code: str,
    idx_cl_code: str,
    on_error_013: str = "skip",
) -> tuple[int, str]:
    """Fetch and store indicator data for a batch of companies.

    Args:
        client: DART API client
        session: Database session
        corp_codes: List of company codes (max 100)
        year: Reporting year
        report_code: Report code
        idx_cl_code: Indicator category code
        on_error_013: How to handle "no data" errors

    Returns:
        Tuple of (records_inserted, status)
    """
    try:
        df = client.fnltt_cmpny_indx(corp_codes, year, report_code, idx_cl_code)

        if df.empty:
            logger.info(f"No data for {len(corp_codes)} corps {year} {report_code} {idx_cl_code}")
            return 0, "no_data"

        records = transform_indicator_data(df, year, report_code)

        if not records:
            return 0, "no_records"

        # Use PostgreSQL upsert (ON CONFLICT DO UPDATE for new data)
        stmt = insert(FinancialIndicator).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "corp_code",
                "year",
                "report_code",
                "idx_code",
            ],
            set_={
                "stock_code": stmt.excluded.stock_code,
                "settlement_date": stmt.excluded.settlement_date,
                "idx_cl_code": stmt.excluded.idx_cl_code,
                "idx_cl_name": stmt.excluded.idx_cl_name,
                "idx_name": stmt.excluded.idx_name,
                "idx_value": stmt.excluded.idx_value,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )

        result = session.execute(stmt)
        session.commit()

        inserted = result.rowcount if result.rowcount else len(records)
        logger.info(f"Upserted {inserted} records for {year} {report_code} {idx_cl_code}")

        return inserted, "success"

    except DartError as e:
        if e.code == DartErrorCode.NO_DATA.value:
            logger.info(f"No data available for {year} {report_code} {idx_cl_code}")
            if on_error_013 == "skip":
                return 0, "skipped"
            elif on_error_013 == "stop":
                return 0, "stopped"
            else:
                return 0, "skipped"

        elif e.code == DartErrorCode.RATE_LIMIT.value:
            logger.warning(f"Rate limit hit for {year} {report_code} {idx_cl_code}")
            return 0, "rate_limited"

        else:
            logger.error(f"DART error for {year} {report_code} {idx_cl_code}: {e}")
            return 0, f"error_{e.code}"

    except Exception as e:
        logger.error(f"Unexpected error for {year} {report_code} {idx_cl_code}: {e}")
        session.rollback()
        return 0, "error"


def get_years_to_backfill(start_year: int = EARLIEST_YEAR) -> list[int]:
    """Get list of years to backfill from start_year to current year.

    Note: Data only available from 2023 Q3 onwards.
    """
    effective_start = max(start_year, EARLIEST_YEAR)
    current_year = datetime.now().year
    return list(range(effective_start, current_year + 1))


def get_report_codes_for_year(year: int) -> list[str]:
    """Get list of report codes to fetch for a given year.

    For 2023, only Q3 and Q4 are available.
    """
    codes = list(REPORT_CODES.keys())

    if year == EARLIEST_YEAR:
        # Only Q3 (11014) and Annual (11011) available for 2023
        return ["11014", "11011"]

    return codes


def get_indicator_categories() -> list[str]:
    """Get list of indicator category codes to fetch."""
    return list(INDICATOR_CATEGORIES.keys())


def _chunk_list(lst: list, chunk_size: int) -> Generator[list, None, None]:
    """Split a list into chunks of specified size."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def _record_progress(
    session: Session,
    corp_code: str,
    year: int,
    report_code: str,
    idx_cl_code: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Record indicator backfill progress."""
    stmt = insert(IndicatorBackfillProgress).values(
        corp_code=corp_code,
        year=year,
        report_code=report_code,
        idx_cl_code=idx_cl_code,
        status=status,
        error_message=error_message,
        processed_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["corp_code", "year", "report_code", "idx_cl_code"],
        set_={
            "status": status,
            "error_message": error_message,
            "processed_at": datetime.utcnow(),
        },
    )
    session.execute(stmt)
    session.commit()


def backfill_indicators(
    client: DartClient,
    session: Session,
    corp_codes: list[str] | None = None,
    start_year: int = EARLIEST_YEAR,
    on_error_013: str = "skip",
    batch_size: int = 100,
) -> dict:
    """Backfill financial indicators for companies.

    Args:
        client: DART API client
        session: Database session
        corp_codes: List of company codes (if None, use all priority companies)
        start_year: Year to start backfill from (min 2023)
        on_error_013: How to handle "no data" errors
        batch_size: Number of companies per API request (max 100)

    Returns:
        Dictionary with stats (total_records, errors, etc.)
    """
    stats = {
        "total_records": 0,
        "successful_batches": 0,
        "skipped": 0,
        "errors": 0,
        "rate_limited": False,
    }

    # Get companies if not provided
    if corp_codes is None:
        companies = list(get_companies_for_backfill(session, priority_only=True))
        corp_codes = [c.corp_code for c in companies]

    if not corp_codes:
        logger.warning("No companies to backfill")
        return stats

    years = get_years_to_backfill(start_year)
    indicator_categories = get_indicator_categories()

    # Chunk companies into batches (max 100 per API call)
    company_batches = list(_chunk_list(corp_codes, min(batch_size, 100)))
    logger.info(f"Processing {len(corp_codes)} companies in {len(company_batches)} batches")

    for year in years:
        report_codes = get_report_codes_for_year(year)

        for report_code in report_codes:
            for idx_cl_code in indicator_categories:
                for batch in company_batches:
                    # Check if already processed (using first corp in batch as marker)
                    existing = session.execute(
                        select(IndicatorBackfillProgress).where(
                            IndicatorBackfillProgress.corp_code == batch[0],
                            IndicatorBackfillProgress.year == year,
                            IndicatorBackfillProgress.report_code == report_code,
                            IndicatorBackfillProgress.idx_cl_code == idx_cl_code,
                            IndicatorBackfillProgress.status == "completed",
                        )
                    ).scalar_one_or_none()

                    if existing:
                        logger.debug(f"Skipping already processed {year} {report_code} {idx_cl_code}")
                        continue

                    records, status = fetch_indicators_batch(
                        client, session, batch, year, report_code, idx_cl_code, on_error_013
                    )

                    stats["total_records"] += records

                    if status == "success":
                        stats["successful_batches"] += 1
                        # Record progress for each company in batch
                        for corp_code in batch:
                            _record_progress(
                                session, corp_code, year, report_code, idx_cl_code, "completed"
                            )
                    elif status in ("skipped", "no_data", "no_records"):
                        stats["skipped"] += 1
                    elif status == "rate_limited":
                        stats["rate_limited"] = True
                        # Record progress and stop
                        for corp_code in batch:
                            _record_progress(
                                session, corp_code, year, report_code, idx_cl_code, "rate_limited"
                            )
                        return stats
                    else:
                        stats["errors"] += 1
                        for corp_code in batch:
                            _record_progress(
                                session, corp_code, year, report_code, idx_cl_code, "failed", status
                            )

    return stats


def backfill_single_company(
    client: DartClient,
    session: Session,
    corp_code: str,
    start_year: int = EARLIEST_YEAR,
    on_error_013: str = "skip",
) -> dict:
    """Backfill all indicator data for a single company.

    Args:
        client: DART API client
        session: Database session
        corp_code: Company code
        start_year: Year to start backfill from
        on_error_013: How to handle "no data" errors

    Returns:
        Dictionary with stats
    """
    return backfill_indicators(
        client,
        session,
        corp_codes=[corp_code],
        start_year=start_year,
        on_error_013=on_error_013,
        batch_size=1,
    )


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
