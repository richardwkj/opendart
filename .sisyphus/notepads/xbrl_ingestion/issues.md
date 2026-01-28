# Issues: XBRL Notes Ingestion

## Known Gotchas
- XBRL files can be 10-50MB each - must use temp directory cleanup
- Not all reports have text blocks - handle gracefully
- `rcept_no` lookup required before XBRL download
- Text content may be HTML-formatted, not plain text
