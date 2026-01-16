# Repository Guidelines

## Project Structure & Module Organization
- `src/opendart/` holds the core package: `api.py` (DART client), `config.py` (env settings), `db.py` (SQLAlchemy sessions), and `models.py` (ORM models).
- `src/opendart/etl/` contains the ETL flows for financials and events (`financials.py`, `events.py`).
- `alembic/` and `alembic.ini` manage database migrations.
- `tests/` is reserved for pytest tests (currently minimal).
- `spec.md` captures the product/system specification and domain rules.

## Build, Test, and Development Commands
- `uv sync` (if you use uv) or `pip install -e .` to install dependencies from `pyproject.toml`.
- `python -m pytest` to run the test suite.
- `python -m pytest --cov=opendart` for optional coverage reporting (requires `pytest-cov`).
- `alembic revision --autogenerate -m "describe change"` to generate a migration (needs `DATABASE_URL`).
- `alembic upgrade head` to apply migrations to the target database.

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indentation, and type hints are standard throughout the codebase.
- Use `snake_case` for functions/modules, `CamelCase` for classes, and `UPPER_SNAKE` for constants.
- Preserve domain naming (`corp_code`, `stock_code`, `report_code`, `fs_div`) to match DART semantics.

## Testing Guidelines
- Use pytest; add tests under `tests/` with filenames like `test_*.py`.
- Run `python -m pytest` every time a script is completed before marking work done.
- Cover ETL transforms (e.g., parsing, normalization) and DB upserts where practical.

## Commit & Pull Request Guidelines
- Git history is minimal (only an initial commit), so no established convention yet; keep messages short and imperative.
- PRs should include a brief summary, testing notes, and any migration or config changes.
- For data-model changes, include the migration command used and any backfill considerations.

## Configuration & Secrets
- Create a `.env` file with `DART_API_KEY` and `DATABASE_URL` (never commit secrets).
- Rate-limiting and backfill defaults live in `src/opendart/config.py`; keep changes explicit.
