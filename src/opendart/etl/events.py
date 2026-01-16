"""ETL module for key events data."""

import logging
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from opendart.api import DartClient, DartError
from opendart.models import KeyEvent

logger = logging.getLogger(__name__)


def parse_date(value: str | None) -> date | None:
    """Parse date from DART format (YYYYMMDD)."""
    if not value or pd.isna(value):
        return None

    try:
        return datetime.strptime(str(value), "%Y%m%d").date()
    except ValueError:
        logger.warning(f"Could not parse date: {value}")
        return None


def transform_events_data(df: pd.DataFrame) -> list[dict]:
    """Transform DART events data to model format.

    Args:
        df: DataFrame from list()

    Returns:
        List of dicts ready for insertion
    """
    if df.empty:
        return []

    records = []

    for _, row in df.iterrows():
        rcept_no = row.get("rcept_no")
        if not rcept_no:
            continue

        corp_code = row.get("corp_code", row.get("corp_cls", ""))
        report_nm = row.get("report_nm", "")
        rcept_dt = row.get("rcept_dt")

        event_date = parse_date(rcept_dt)
        if not event_date:
            continue

        records.append(
            {
                "rcept_no": str(rcept_no),
                "corp_code": str(corp_code),
                "report_nm": str(report_nm)[:255],  # Truncate if needed
                "event_date": event_date,
            }
        )

    return records


def fetch_company_events(
    client: DartClient,
    session: Session,
    corp_code: str,
    start_date: str,
    end_date: str,
    kind: str | None = None,
) -> tuple[int, str]:
    """Fetch and store events for a company.

    Args:
        client: DART API client
        session: Database session
        corp_code: Company code
        start_date: Start date YYYYMMDD
        end_date: End date YYYYMMDD
        kind: Event type filter (B=major issues, etc.)

    Returns:
        Tuple of (records_inserted, status)
    """
    try:
        df = client.list(
            corp_code=corp_code,
            start=start_date,
            end=end_date,
            kind=kind,
        )

        if df.empty:
            logger.info(f"No events for {corp_code} {start_date}-{end_date}")
            return 0, "no_data"

        records = transform_events_data(df)

        if not records:
            return 0, "no_records"

        # Use PostgreSQL upsert (ON CONFLICT DO NOTHING for duplicates)
        stmt = insert(KeyEvent).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["rcept_no"])

        result = session.execute(stmt)
        session.commit()

        inserted = result.rowcount if result.rowcount else len(records)
        logger.info(f"Inserted {inserted} events for {corp_code}")

        return inserted, "success"

    except DartError as e:
        logger.error(f"DART error fetching events for {corp_code}: {e}")
        return 0, f"error_{e.code}"

    except Exception as e:
        logger.error(f"Unexpected error fetching events for {corp_code}: {e}")
        session.rollback()
        return 0, "error"


def fetch_all_events(
    client: DartClient,
    session: Session,
    start_date: str,
    end_date: str,
    kinds: list[str] | None = None,
) -> dict:
    """Fetch all events across all companies for a date range.

    Args:
        client: DART API client
        session: Database session
        start_date: Start date YYYYMMDD
        end_date: End date YYYYMMDD
        kinds: List of event types to fetch

    Returns:
        Dictionary with stats
    """
    if kinds is None:
        # Default: major issues (B) and all types
        kinds = ["B", ""]

    stats = {
        "total_records": 0,
        "successful": 0,
        "errors": 0,
    }

    for kind in kinds:
        try:
            df = client.list(
                start=start_date,
                end=end_date,
                kind=kind if kind else None,
            )

            if df.empty:
                continue

            records = transform_events_data(df)

            if not records:
                continue

            stmt = insert(KeyEvent).values(records)
            stmt = stmt.on_conflict_do_nothing(index_elements=["rcept_no"])

            result = session.execute(stmt)
            session.commit()

            inserted = result.rowcount if result.rowcount else len(records)
            stats["total_records"] += inserted
            stats["successful"] += 1

            logger.info(f"Fetched {inserted} events for kind={kind}")

        except Exception as e:
            logger.error(f"Error fetching events kind={kind}: {e}")
            stats["errors"] += 1
            session.rollback()

    return stats


def sync_recent_events(
    client: DartClient,
    session: Session,
    days: int = 31,
) -> dict:
    """Sync events from the past N days.

    Args:
        client: DART API client
        session: Database session
        days: Number of days to look back

    Returns:
        Dictionary with stats
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    logger.info(f"Syncing events from {start_str} to {end_str}")

    return fetch_all_events(client, session, start_str, end_str)
