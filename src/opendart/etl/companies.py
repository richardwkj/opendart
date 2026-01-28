"""Company ingestion and delisting update helpers."""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from opendart.models import Company

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opendart.api import DartClient

logger = logging.getLogger(__name__)

_DATE_FORMATS = ("%Y-%m-%d", "%Y%m%d")


def _parse_date(value: str | None) -> date | None:
    """Parse dates from common CSV formats (YYYY-MM-DD or YYYYMMDD)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    logger.warning("Unrecognized date format: %s", value)
    return None


def _parse_bool(value: Any, default: bool = False) -> bool:
    """Parse boolean values from common CSV representations."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if not text:
        return default

    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False

    return default


def _normalize_code(value: Any, width: int) -> str | None:
    """Normalize numeric codes while preserving leading zeros."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]

    text = text.replace(",", "")

    if text.isdigit() and width and len(text) < width:
        text = text.zfill(width)

    return text


def _read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    """Read CSV rows as dictionaries."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file is missing headers")
        return [row for row in reader]


def _require_headers(rows: Iterable[dict[str, str]], required: set[str]) -> None:
    """Validate required headers exist in the CSV rows."""
    headers: set[str] = set()
    for row in rows:
        headers.update(row.keys())
        break

    missing = required - headers
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")


def ingest_companies_from_csv(
    session: Session,
    csv_path: str | Path,
    on_stock_code_reuse: str = "reject",
    default_is_priority: bool = False,
) -> dict[str, int]:
    """Ingest new companies from a CSV file.

    Required columns: corp_code, corp_name
    Optional columns: stock_code, listing_date, is_priority

    Stock code reuse handling:
    - "reassign": clear the old company's stock_code when it is delisted.
    - "reject": skip the new row when a reused stock_code is detected.
    """
    if on_stock_code_reuse not in {"reassign", "reject"}:
        raise ValueError("on_stock_code_reuse must be 'reassign' or 'reject'")

    rows = _read_csv_rows(csv_path)
    _require_headers(rows, {"corp_code", "corp_name"})

    stats: dict[str, int] = {
        "total_rows": len(rows),
        "created": 0,
        "skipped_duplicates": 0,
        "skipped_invalid": 0,
        "skipped_stock_conflicts": 0,
        "reassigned_stock_codes": 0,
        "errors": 0,
    }

    seen_corp_codes: set[str] = set()

    for row in rows:
        try:
            corp_code = _normalize_code(row.get("corp_code"), 8)
            corp_name = (row.get("corp_name") or "").strip()

            if not corp_code or not corp_name:
                stats["skipped_invalid"] += 1
                continue

            if corp_code in seen_corp_codes:
                stats["skipped_duplicates"] += 1
                continue

            seen_corp_codes.add(corp_code)

            if session.get(Company, corp_code):
                stats["skipped_duplicates"] += 1
                continue

            stock_code = _normalize_code(row.get("stock_code"), 6)
            listing_date = _parse_date(row.get("listing_date"))
            is_priority = _parse_bool(row.get("is_priority"), default_is_priority)

            if stock_code:
                existing_stock = session.execute(
                    select(Company).where(Company.stock_code == stock_code)
                ).scalar_one_or_none()

                if existing_stock and existing_stock.corp_code != corp_code:
                    if existing_stock.delisted_date is None:
                        stats["skipped_stock_conflicts"] += 1
                        continue

                    if on_stock_code_reuse == "reassign":
                        existing_stock.stock_code = None
                        stats["reassigned_stock_codes"] += 1
                    else:
                        stats["skipped_stock_conflicts"] += 1
                        continue

            company = Company(
                corp_code=corp_code,
                stock_code=stock_code,
                corp_name=corp_name[:255],
                is_priority=is_priority,
                listing_date=listing_date,
            )
            session.add(company)
            stats["created"] += 1
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to ingest row %s: %s", row, exc)
            stats["errors"] += 1

    session.commit()
    return stats


def ingest_companies_by_stock_code(
    client: "DartClient",
    session: Session,
    csv_path: str | Path,
    stock_code_column: str = "Stock_code",
    name_column: str = "Name",
    default_is_priority: bool = True,
) -> dict[str, int]:
    """Ingest companies from a CSV that only has stock_code (not corp_code).

    Looks up corp_code from DART API using the stock_code, then ingests.

    Required columns: stock_code column (configurable), name column (configurable)

    Args:
        client: DartClient instance for API calls
        session: SQLAlchemy session
        csv_path: Path to CSV file
        stock_code_column: Column name for stock codes (default: "Stock_code")
        name_column: Column name for company names (default: "Name")
        default_is_priority: Default priority flag for new companies

    Returns:
        Stats dict with ingestion results
    """
    rows = _read_csv_rows(csv_path)

    # Validate headers
    headers = set(rows[0].keys()) if rows else set()
    if stock_code_column not in headers:
        raise ValueError(f"CSV is missing required column: {stock_code_column}")

    stats: dict[str, int] = {
        "total_rows": len(rows),
        "created": 0,
        "skipped_duplicates": 0,
        "skipped_not_found": 0,
        "skipped_invalid": 0,
        "errors": 0,
    }

    # Fetch all corp_codes from DART and build stock_code -> corp_code mapping
    logger.info("Fetching company codes from DART API...")
    all_corps = client.corp_codes()

    if all_corps.empty:
        logger.error("Failed to fetch company codes from DART API")
        stats["errors"] = len(rows)
        return stats

    # Build lookup: stock_code -> (corp_code, corp_name)
    corp_lookup: dict[str, tuple[str, str]] = {}
    for _, row in all_corps.iterrows():
        stock = row.get("stock_code")
        if stock and str(stock).strip():
            corp_lookup[str(stock).strip().zfill(6)] = (
                str(row["corp_code"]).strip(),
                str(row.get("corp_name", "")).strip(),
            )

    logger.info(f"Built lookup with {len(corp_lookup)} listed companies")

    seen_corp_codes: set[str] = set()

    for row in rows:
        try:
            raw_stock_code = row.get(stock_code_column)
            csv_name = (row.get(name_column) or "").strip()

            stock_code = _normalize_code(raw_stock_code, 6)
            if not stock_code:
                stats["skipped_invalid"] += 1
                continue

            # Look up corp_code from DART data
            if stock_code not in corp_lookup:
                logger.warning(f"Stock code {stock_code} ({csv_name}) not found in DART")
                stats["skipped_not_found"] += 1
                continue

            corp_code, dart_name = corp_lookup[stock_code]

            if corp_code in seen_corp_codes:
                stats["skipped_duplicates"] += 1
                continue

            seen_corp_codes.add(corp_code)

            # Check if already exists in DB
            if session.get(Company, corp_code):
                stats["skipped_duplicates"] += 1
                continue

            # Use DART name (official) over CSV name
            company = Company(
                corp_code=corp_code,
                stock_code=stock_code,
                corp_name=(dart_name or csv_name)[:255],
                is_priority=default_is_priority,
            )
            session.add(company)
            stats["created"] += 1
            logger.debug(f"Added {corp_code} ({stock_code}): {dart_name}")

        except Exception as exc:
            logger.exception("Failed to process row %s: %s", row, exc)
            stats["errors"] += 1

    session.commit()
    logger.info(
        f"Ingestion complete: {stats['created']} created, "
        f"{stats['skipped_not_found']} not found, "
        f"{stats['skipped_duplicates']} duplicates"
    )
    return stats


def apply_delisting_updates_from_csv(
    session: Session,
    csv_path: str | Path,
) -> dict[str, int]:
    """Apply delisting updates from a CSV file.

    Required columns: corp_code, delisted_date
    """
    rows = _read_csv_rows(csv_path)
    _require_headers(rows, {"corp_code", "delisted_date"})

    stats: dict[str, int] = {
        "total_rows": len(rows),
        "updated": 0,
        "skipped_invalid": 0,
        "missing_company": 0,
        "errors": 0,
    }

    for row in rows:
        try:
            corp_code = _normalize_code(row.get("corp_code"), 8)
            delisted_date = _parse_date(row.get("delisted_date"))

            if not corp_code or not delisted_date:
                stats["skipped_invalid"] += 1
                continue

            company = session.get(Company, corp_code)
            if not company:
                stats["missing_company"] += 1
                continue

            company.delisted_date = delisted_date
            stats["updated"] += 1
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to apply delisting update %s: %s", row, exc)
            stats["errors"] += 1

    session.commit()
    return stats
