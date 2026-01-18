"""Scheduler module for automated monthly sync jobs.

Per spec section 6: Monthly schedule on the 1st of the month at 02:00 KST.
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from opendart.api import DartClient
from opendart.db import get_session
from opendart.etl.events import sync_recent_events
from opendart.etl.financials import backfill_company, get_companies_for_backfill
from opendart.notifications import notify_job_failure, notify_sync_complete

logger = logging.getLogger(__name__)


def monthly_sync_job(
    on_error_013: str = "skip",
    days_lookback: int = 31,
) -> dict:
    """Execute the monthly sync job.

    Per spec section 6.3:
    1. For each company, compare last_updated with current time
    2. Fetch disclosures and financial data from past 31 days
    3. Upsert records and update last_updated

    Args:
        on_error_013: How to handle no-data errors
        days_lookback: Days to look back for new data

    Returns:
        Dictionary with job statistics
    """
    logger.info(f"Starting monthly sync job at {datetime.now()}")

    stats = {
        "financials_records": 0,
        "financials_companies": 0,
        "financials_errors": 0,
        "events_records": 0,
        "events_errors": 0,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
    }

    client = DartClient()
    current_year = datetime.now().year

    try:
        with get_session() as session:
            # Step 1 & 2: Process financial data for recent period
            for company in get_companies_for_backfill(session, priority_only=False):
                try:
                    result = backfill_company(
                        client,
                        session,
                        company.corp_code,
                        start_year=current_year,  # Only current year for monthly sync
                        on_error_013=on_error_013,
                    )
                    stats["financials_records"] += result.get("total_records", 0)
                    stats["financials_companies"] += 1

                    # Update last_updated timestamp
                    company.last_updated = datetime.utcnow()
                    session.commit()

                    if result.get("rate_limited"):
                        logger.warning("Rate limit hit during monthly sync; stopping.")
                        break

                except Exception as e:
                    logger.error(f"Error processing company {company.corp_code}: {e}")
                    stats["financials_errors"] += 1

            # Step 2: Sync key events from past N days
            try:
                events_result = sync_recent_events(client, session, days=days_lookback)
                stats["events_records"] = events_result.get("total_records", 0)
            except Exception as e:
                logger.error(f"Error syncing events: {e}")
                stats["events_errors"] += 1

    except Exception as e:
        logger.exception(f"Monthly sync job failed: {e}")
        notify_job_failure("monthly_sync", e, context=stats)
        raise

    stats["completed_at"] = datetime.now().isoformat()
    logger.info(f"Monthly sync job completed: {stats}")

    # Send success notification
    notify_sync_complete(stats)

    return stats


def create_scheduler() -> BlockingScheduler:
    """Create and configure the APScheduler instance.

    Returns:
        Configured BlockingScheduler
    """
    scheduler = BlockingScheduler(timezone="Asia/Seoul")

    # Schedule monthly job: 1st of each month at 02:00 KST
    scheduler.add_job(
        monthly_sync_job,
        CronTrigger(day=1, hour=2, minute=0, timezone="Asia/Seoul"),
        id="monthly_sync",
        name="Monthly DART data sync",
        replace_existing=True,
    )

    logger.info("Scheduler configured: monthly sync on 1st at 02:00 KST")

    return scheduler


def run_scheduler() -> None:
    """Start the scheduler (blocking)."""
    scheduler = create_scheduler()

    logger.info("Starting scheduler...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
