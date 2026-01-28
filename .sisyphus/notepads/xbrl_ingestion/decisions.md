# Decisions: XBRL Notes Ingestion

## [2026-01-28] Library Choice
**Decision**: Use `opendartreader` + `arelle-release` instead of `dart-fss`
**Reasoning**: 
- `opendartreader` already in project, supports XBRL download via `finstate_xml()`
- `dart-fss` introduces separate rate limiter (0.2s) conflicting with existing `DartClient` (0.15s)
- Arelle direct provides full control over text block extraction

## [2026-01-28] Storage Strategy
**Decision**: Store extracted text only in `financial_notes` table
**Reasoning**: User preference, no need for raw ZIP files

## [2026-01-28] Scope
**Decision**: XBRL Text Blocks (Notes) only, no MD&A
**Reasoning**: MD&A is in HTML/PDF documents, not XBRL structure
