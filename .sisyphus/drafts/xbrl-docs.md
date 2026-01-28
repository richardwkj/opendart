# Draft: XBRL Parser Documentation

## Requirements (confirmed)
- Create a markdown file showing entity relationships based on `src/opendart/etl/xbrl.py`
- Format: ASCII diagrams and text descriptions (User explicitly requested ASCII)
- Scope: The XBRL parsing logic and data flow

## Technical Decisions
- **Target File**: `docs/XBRL_PARSER.md`
- **Diagram Style**: ASCII (Monospace block diagrams)
- **Key Components to Document**:
    - `DartClient` (Source)
    - `rcept_no` (Linkage key)
    - `Arelle/ModelXbrl` (Parser)
    - `TextBlock` (Internal Structure)
    - `FinancialNote` (DB Model)

## Plan Structure
1. **Overview**: High-level purpose
2. **Data Flow Diagram**: ASCII flowchart
3. **Entity Relationship Diagram**: ASCII ERD-style
4. **Component Descriptions**: Detailed text
