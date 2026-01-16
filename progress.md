# Progress

Based on `spec.md` and `CLAUDE.md`, this checklist tracks what is implemented versus still needed.

## Completed
- [x] Configuration loader for `.env` (`DART_API_KEY`, `DATABASE_URL`) with defaults in `src/opendart/config.py`.
- [x] DART API wrapper with rate limiting and error handling in `src/opendart/api.py`.
- [x] Core database models (`companies`, `financial_fundamentals`, `key_events`, `backfill_progress`) with constraints in `src/opendart/models.py`.
- [x] Financial ETL transforms + upsert logic in `src/opendart/etl/financials.py`.
- [x] Events ETL transforms + upsert logic in `src/opendart/etl/events.py`.
- [x] Alembic configuration scaffold (`alembic/`, `alembic.ini`).

## In Progress / Partial
- [ ] CLI entrypoint (`opendart` script in `pyproject.toml`) is declared but `src/opendart/cli.py` is missing.
- [ ] Alembic migration history is empty (`alembic/versions/` has no revisions).
- [ ] Tests are only a placeholder (`tests/` has no real test cases).
- [ ] Priority ordering exists in `get_companies_for_backfill`, but no full pipeline to run scheduled backfills.
- [ ] CSV company ingestion and delisting helpers exist in `src/opendart/etl/companies.py`, but no CLI/workflow wiring yet.
- [ ] Stock code reuse handling exists via `on_stock_code_reuse`, but needs a user-facing decision flow.

## Not Started / Missing vs Spec
- [ ] Scheduler/automation for monthly runs (APScheduler/Cron/GitHub Actions).
- [ ] Rate-limit handling workflow (pause for 1 hour vs exit) and error logging to the level described in the spec.
- [ ] Latest_Financials view creation and migrations.
- [ ] Failure notification (e.g., email alerts).
- [ ] Optional tracking for earliest data year on no-data errors (spec section 5.2).
