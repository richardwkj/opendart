"""Command-line interface for OpenDART ETL tasks."""

from __future__ import annotations

import logging
import time
from typing import Any

import click

from opendart.api import DartClient
from opendart.db import get_session, init_db
from opendart.etl.companies import (
    apply_delisting_updates_from_csv,
    ingest_companies_from_csv,
)
from opendart.etl.events import sync_recent_events
from opendart.etl.financials import backfill_company, get_companies_for_backfill
from opendart.scheduler import monthly_sync_job, run_scheduler

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _print_stats(stats: dict[str, Any], heading: str | None = None) -> None:
    if heading:
        click.echo(heading)
    for key, value in stats.items():
        click.echo(f"{key}: {value}")


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    show_default=True,
)
def cli(log_level: str) -> None:
    """OpenDART ETL command group."""
    _configure_logging(log_level)


@cli.command("init-db")
def init_db_command() -> None:
    """Initialize database tables using SQLAlchemy metadata."""
    init_db()
    click.echo("Database initialized.")


@cli.command("ingest-companies")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--on-stock-code-reuse",
    type=click.Choice(["reassign", "reject"], case_sensitive=False),
    default="reject",
    show_default=True,
)
@click.option(
    "--default-priority/--no-default-priority",
    default=False,
    show_default=True,
    help="Fallback priority flag when CSV does not provide is_priority.",
)
def ingest_companies_command(
    csv_path: str,
    on_stock_code_reuse: str,
    default_priority: bool,
) -> None:
    """Ingest new companies from a CSV file."""
    with get_session() as session:
        stats = ingest_companies_from_csv(
            session,
            csv_path,
            on_stock_code_reuse=on_stock_code_reuse.lower(),
            default_is_priority=default_priority,
        )

    _print_stats(stats, heading="Ingestion summary")


@cli.command("update-delistings")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def update_delistings_command(csv_path: str) -> None:
    """Apply delisting updates from a CSV file."""
    with get_session() as session:
        stats = apply_delisting_updates_from_csv(session, csv_path)

    _print_stats(stats, heading="Delisting update summary")


@cli.command("backfill")
@click.option("--corp-code", help="Optional corp_code to backfill a single company.")
@click.option("--start-year", default=2015, show_default=True, type=int)
@click.option(
    "--priority-only",
    is_flag=True,
    help="Only backfill companies marked as priority.",
)
@click.option(
    "--on-error-013",
    type=click.Choice(["skip", "mark", "stop"], case_sensitive=False),
    default="skip",
    show_default=True,
    help="Action on no-data errors: skip, mark (set earliest_data_year), or stop.",
)
@click.option(
    "--on-rate-limit",
    type=click.Choice(["pause", "exit", "prompt"], case_sensitive=False),
    default="prompt",
    show_default=True,
    help="Action on rate limit: pause (wait 1hr), exit (stop gracefully), prompt (ask user).",
)
def backfill_command(
    corp_code: str | None,
    start_year: int,
    priority_only: bool,
    on_error_013: str,
    on_rate_limit: str,
) -> None:
    """Backfill financial fundamentals."""
    client = DartClient()

    if corp_code:
        with get_session() as session:
            stats = backfill_company(
                client,
                session,
                corp_code,
                start_year=start_year,
                on_error_013=on_error_013.lower(),
            )
        _print_stats(stats, heading=f"Backfill summary for {corp_code}")
        return

    aggregate = {
        "total_records": 0,
        "successful": 0,
        "skipped": 0,
        "errors": 0,
        "rate_limited": False,
    }

    with get_session() as session:
        companies = list(get_companies_for_backfill(session, priority_only=priority_only))
        company_idx = 0

        while company_idx < len(companies):
            company = companies[company_idx]
            click.echo(f"Backfilling {company.corp_code}...")
            stats = backfill_company(
                client,
                session,
                company.corp_code,
                start_year=start_year,
                on_error_013=on_error_013.lower(),
            )

            aggregate["total_records"] += stats.get("total_records", 0)
            aggregate["successful"] += stats.get("successful", 0)
            aggregate["skipped"] += stats.get("skipped", 0)
            aggregate["errors"] += stats.get("errors", 0)

            if stats.get("rate_limited"):
                aggregate["rate_limited"] = True
                action = on_rate_limit.lower()

                if action == "prompt":
                    click.echo("\nRate limit hit (Error 020).")
                    action = click.prompt(
                        "Choose action",
                        type=click.Choice(["pause", "exit"], case_sensitive=False),
                        default="exit",
                    )

                if action == "pause":
                    click.echo("Pausing for 1 hour before resuming...")
                    logger.info("Rate limit hit; pausing for 1 hour")
                    time.sleep(3600)  # 1 hour
                    click.echo("Resuming backfill...")
                    # Don't increment company_idx; retry the same company
                    continue
                else:
                    click.echo("Exiting gracefully. Progress has been saved.")
                    logger.info("Rate limit hit; exiting. Progress saved to backfill_progress table.")
                    break

            company_idx += 1

    _print_stats(aggregate, heading="Backfill summary")


@cli.command("sync-events")
@click.option(
    "--days",
    default=31,
    show_default=True,
    type=int,
    help="Number of days to look back for events.",
)
def sync_events_command(days: int) -> None:
    """Sync key events from the past N days."""
    client = DartClient()

    with get_session() as session:
        stats = sync_recent_events(client, session, days=days)

    _print_stats(stats, heading="Events sync summary")


@cli.command("run-scheduler")
def run_scheduler_command() -> None:
    """Start the APScheduler for automated monthly syncs.

    Runs the scheduler in blocking mode. The monthly sync job executes
    on the 1st of each month at 02:00 KST.
    """
    click.echo("Starting scheduler (monthly sync on 1st at 02:00 KST)...")
    click.echo("Press Ctrl+C to stop.")
    run_scheduler()


@cli.command("run-sync")
@click.option(
    "--on-error-013",
    type=click.Choice(["skip", "mark", "stop"], case_sensitive=False),
    default="skip",
    show_default=True,
)
@click.option(
    "--days",
    default=31,
    show_default=True,
    type=int,
    help="Days to look back for events.",
)
def run_sync_command(on_error_013: str, days: int) -> None:
    """Run the monthly sync job immediately (manual trigger)."""
    click.echo("Running monthly sync job...")
    stats = monthly_sync_job(on_error_013=on_error_013.lower(), days_lookback=days)
    _print_stats(stats, heading="Monthly sync summary")


if __name__ == "__main__":
    cli()
