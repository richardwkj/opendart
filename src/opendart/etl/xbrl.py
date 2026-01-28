"""ETL module for XBRL text block ingestion."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypedDict, cast

from arelle import Cntlr, ModelXbrl
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult

from ..api import DartClient, DartError, DartErrorCode
from ..db import get_session
from ..models import FinancialNote

logger = logging.getLogger(__name__)

_EXCLUDED_INSTANCE_SUFFIXES = ("_cal.xml", "_def.xml", "_pre.xml", "_lab.xml")


class SeriesLike(Protocol):
    def astype(self, dtype: type[str]) -> SeriesLike: ...

    def eq(self, other: object) -> SeriesLike: ...


class ColumnsLike(Protocol):
    def __contains__(self, item: object) -> bool: ...


class RowLike(Protocol):
    def get(self, key: str, default: object | None = None) -> object: ...


class LocIndexer(Protocol):
    def __getitem__(self, key: SeriesLike) -> DataFrameLike: ...


class ILocIndexer(Protocol):
    def __getitem__(self, index: int) -> RowLike: ...


class DataFrameLike(Protocol):
    @property
    def empty(self) -> bool: ...

    @property
    def columns(self) -> ColumnsLike: ...

    def __getitem__(self, key: str) -> SeriesLike: ...

    @property
    def loc(self) -> LocIndexer: ...

    @property
    def iloc(self) -> ILocIndexer: ...

    def sort_values(self, *, by: str, ascending: bool = True) -> DataFrameLike: ...


class TextBlock(TypedDict):
    concept_id: str
    title: str
    content: str
    context_ref: str


class FinancialNoteRecord(TypedDict):
    corp_code: str
    rcept_no: str
    year: int
    report_code: str
    fetched_at: datetime
    concept_id: str
    title: str
    content: str
    context_ref: str


def _find_instance_file(root: Path) -> Path | None:
    candidates: list[Path] = []
    for path in root.rglob("*.xml"):
        name = path.name.lower()
        if name.endswith(_EXCLUDED_INSTANCE_SUFFIXES):
            continue
        candidates.append(path)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item.name)
    return candidates[0]


def _extract_text_blocks(model_xbrl: ModelXbrl) -> list[TextBlock]:
    blocks_by_concept: dict[str, TextBlock] = {}

    for fact in model_xbrl.facts:
        concept = fact.concept
        if concept is None or concept.type is None:
            continue

        if "textBlock" not in concept.type.name:
            continue

        concept_id = str(concept.qname)
        content = "" if fact.value is None else str(fact.value)
        title = concept.label() or concept_id
        context_ref = fact.contextID or ""

        record: TextBlock = {
            "concept_id": concept_id,
            "title": str(title),
            "content": str(content),
            "context_ref": str(context_ref),
        }

        existing = blocks_by_concept.get(concept_id)
        if existing is None or (not existing["content"] and record["content"]):
            blocks_by_concept[concept_id] = record

    return list(blocks_by_concept.values())


def ingest_xbrl(corp_code: str, year: int, report_code: str) -> dict[str, int]:
    """Ingest XBRL text blocks for a company/report period."""

    stats: dict[str, int] = {
        "total_notes": 0,
        "successful": 0,
        "errors": 0,
    }

    client = DartClient()
    start_date = f"{year}0101"
    end_date = f"{year}1231"

    try:
        df = cast(
            DataFrameLike,
            cast(
                object,
                client.list(
                    corp_code=corp_code,
                    start=start_date,
                    end=end_date,
                    kind="A",
                ),
            ),
        )
    except DartError as e:
        if e.code == DartErrorCode.NO_DATA.value:
            logger.info(f"No disclosures for {corp_code} {year} {report_code}")
            return stats
        logger.error(f"DART error listing disclosures for {corp_code}: {e}")
        stats["errors"] += 1
        return stats
    except Exception as e:
        logger.error(f"Unexpected error listing disclosures for {corp_code}: {e}")
        stats["errors"] += 1
        return stats

    if df.empty:
        logger.info(f"No disclosures for {corp_code} {year} {report_code}")
        return stats

    report_column = None
    for column in ("reprt_code", "report_code"):
        if column in df.columns:
            report_column = column
            break

    if report_column is None:
        logger.warning(f"Disclosure list missing report code column for {corp_code}")
        return stats

    mask = df[report_column].astype(str).eq(str(report_code))
    matching = df.loc[mask]
    if matching.empty:
        logger.info(f"No disclosure matching report_code={report_code} for {corp_code}")
        return stats

    if "rcept_dt" in matching.columns:
        matching = matching.sort_values(by="rcept_dt", ascending=False)

    first_row = matching.iloc[0]
    rcept_no = str(first_row.get("rcept_no", "")).strip()
    if not rcept_no:
        logger.warning(f"Disclosure missing rcept_no for {corp_code} {report_code}")
        return stats

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / f"{rcept_no}.zip"
            _ = client.download_xbrl(rcept_no, str(zip_path))

            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp_dir)

            instance_path = _find_instance_file(Path(temp_dir))
            if instance_path is None:
                logger.info(f"No XBRL instance file for {rcept_no}")
                return stats

            ctrl = Cntlr(logFileName="logToStdErr")
            model_xbrl = ctrl.modelManager.load(str(instance_path))
            if model_xbrl is None:
                logger.error(f"Failed to load XBRL instance for {rcept_no}")
                stats["errors"] += 1
                return stats

            try:
                text_blocks = _extract_text_blocks(model_xbrl)
            finally:
                ctrl.modelManager.close(model_xbrl)

    except DartError as e:
        if e.code == DartErrorCode.NO_DATA.value:
            logger.info(f"No XBRL available for {rcept_no}")
            return stats
        logger.error(f"DART error downloading XBRL for {rcept_no}: {e}")
        stats["errors"] += 1
        return stats
    except Exception as e:
        logger.error(f"Unexpected error processing XBRL for {rcept_no}: {e}")
        stats["errors"] += 1
        return stats

    if not text_blocks:
        logger.info(f"No text blocks found for {rcept_no}")
        return stats

    now = datetime.now(timezone.utc)
    records: list[FinancialNoteRecord] = []
    for block in text_blocks:
        records.append(
            {
                "corp_code": corp_code,
                "rcept_no": rcept_no,
                "year": year,
                "report_code": report_code,
                "fetched_at": now,
                "concept_id": block["concept_id"],
                "title": block["title"],
                "content": block["content"],
                "context_ref": block["context_ref"],
            }
        )
    stats["total_notes"] = len(records)

    try:
        with get_session() as session:
            stmt = insert(FinancialNote).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["corp_code", "rcept_no", "concept_id"],
                set_={
                    "title": stmt.excluded.title,
                    "content": stmt.excluded.content,
                    "context_ref": stmt.excluded.context_ref,
                    "year": stmt.excluded.year,
                    "report_code": stmt.excluded.report_code,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )

            result = cast(CursorResult[tuple[object, ...]], session.execute(stmt))
            session.commit()

    except Exception as e:
        logger.error(f"Database error upserting notes for {rcept_no}: {e}")
        stats["errors"] += 1
        return stats

    stats["successful"] = result.rowcount
    return stats
