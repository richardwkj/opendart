# Learnings: XBRL Notes Ingestion

## Conventions
- Follow existing ETL pattern: return stats dict `{"total_records": N, "errors": N, ...}`
- Use PostgreSQL upserts via `on_conflict_do_update`
- Session management: `with get_session() as session:`
- Rate limiting: All API calls through `DartClient._wait_for_rate_limit()`

## Patterns from Codebase
- Domain naming preserved: `corp_code`, `stock_code`, `report_code`, `fs_div`
- Error handling: `DartErrorCode.NO_DATA` (013), `DartErrorCode.RATE_LIMIT` (020)
- Temp file cleanup: Use `tempfile.TemporaryDirectory()` context manager

## XBRL-Specific
- Text blocks identified by: `fact.concept.type.name` contains `"textBlock"`
- XBRL download requires `rcept_no` (receipt number), not just `corp_code`
- Must lookup `rcept_no` via `client.list()` API first
