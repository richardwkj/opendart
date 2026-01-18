from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from opendart.etl.companies import (
    apply_delisting_updates_from_csv,
    ingest_companies_from_csv,
)
from opendart.models import Base, Company


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_ingest_companies_basic_and_duplicates(tmp_path):
    session = _make_session()
    try:
        existing = Company(corp_code="00000999", stock_code="000999", corp_name="Existing")
        session.add(existing)
        session.commit()

        csv_path = tmp_path / "companies.csv"
        _write_csv(
            csv_path,
            "\n".join(
                [
                    "corp_code,corp_name,stock_code,listing_date,is_priority",
                    "123,Alpha,456,2020-01-02,yes",
                    "123,Alpha Duplicate,456,2020-01-02,yes",
                    "999,Existing,000999,2020-01-02,no",
                    ",Missing,,",
                ]
            )
            + "\n",
        )

        stats = ingest_companies_from_csv(session, csv_path)

        assert stats["created"] == 1
        assert stats["skipped_duplicates"] == 2
        assert stats["skipped_invalid"] == 1

        company = session.get(Company, "00000123")
        assert company is not None
        assert company.stock_code == "000456"
        assert company.listing_date == date(2020, 1, 2)
        assert company.is_priority is True
    finally:
        session.close()


def test_stock_code_reuse_policy(tmp_path):
    session = _make_session()
    try:
        delisted = Company(
            corp_code="00000001",
            stock_code="000111",
            corp_name="Delisted",
            delisted_date=date(2020, 1, 1),
        )
        active = Company(corp_code="00000002", stock_code="000222", corp_name="Active")
        session.add_all([delisted, active])
        session.commit()

        csv_path = tmp_path / "reuse.csv"
        _write_csv(
            csv_path,
            "\n".join(
                [
                    "corp_code,corp_name,stock_code",
                    "3,NewCo,111",
                    "4,Blocked,222",
                ]
            )
            + "\n",
        )

        stats = ingest_companies_from_csv(session, csv_path, on_stock_code_reuse="reassign")

        assert stats["created"] == 1
        assert stats["reassigned_stock_codes"] == 1
        assert stats["skipped_stock_conflicts"] == 1

        reassigned = session.get(Company, "00000001")
        assert reassigned is not None
        assert reassigned.stock_code is None

        new_company = session.get(Company, "00000003")
        assert new_company is not None
        assert new_company.stock_code == "000111"
    finally:
        session.close()


def test_apply_delisting_updates(tmp_path):
    session = _make_session()
    try:
        company = Company(corp_code="00000010", corp_name="TargetCo")
        session.add(company)
        session.commit()

        csv_path = tmp_path / "delistings.csv"
        _write_csv(
            csv_path,
            "\n".join(
                [
                    "corp_code,delisted_date",
                    "10,20240115",
                    "999,20240115",
                ]
            )
            + "\n",
        )

        stats = apply_delisting_updates_from_csv(session, csv_path)

        assert stats["updated"] == 1
        assert stats["missing_company"] == 1

        refreshed = session.get(Company, "00000010")
        assert refreshed is not None
        assert refreshed.delisted_date == date(2024, 1, 15)
    finally:
        session.close()
