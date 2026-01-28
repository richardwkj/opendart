"""SQLAlchemy ORM models for OpenDART ETL."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Company(Base):
    """Master table for companies."""

    __tablename__ = "companies"

    corp_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    stock_code: Mapped[Optional[str]] = mapped_column(
        String(6), unique=True, nullable=True
    )
    corp_name: Mapped[str] = mapped_column(String(255))
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False)
    listing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delisted_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    earliest_data_year: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Earliest year with available DART data (to avoid wasteful queries)"
    )

    # Relationships
    financials: Mapped[list["FinancialFundamental"]] = relationship(
        back_populates="company"
    )
    events: Mapped[list["KeyEvent"]] = relationship(back_populates="company")
    financial_notes: Mapped[list["FinancialNote"]] = relationship(
        back_populates="company"
    )

    def __repr__(self) -> str:
        return f"<Company {self.corp_code} ({self.stock_code}): {self.corp_name}>"


class FinancialFundamental(Base):
    """Detail table for financial statement line items."""

    __tablename__ = "financial_fundamentals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corp_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("companies.corp_code"), index=True
    )
    year: Mapped[int] = mapped_column(Integer)
    report_code: Mapped[str] = mapped_column(String(5))
    fs_div: Mapped[str] = mapped_column(String(3))  # CFS or OFS
    account_id: Mapped[str] = mapped_column(String(200))
    account_name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint(
            "corp_code",
            "year",
            "report_code",
            "fs_div",
            "account_id",
            "version",
            name="unique_financial_entry",
        ),
    )

    # Relationship
    company: Mapped["Company"] = relationship(back_populates="financials")

    def __repr__(self) -> str:
        return (
            f"<Financial {self.corp_code} {self.year} {self.report_code}: "
            f"{self.account_name}={self.amount}>"
        )


class KeyEvent(Base):
    """Detail table for key disclosure events."""

    __tablename__ = "key_events"

    rcept_no: Mapped[str] = mapped_column(String(14), primary_key=True)
    corp_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("companies.corp_code"), index=True
    )
    report_nm: Mapped[str] = mapped_column(String(255))
    event_date: Mapped[date] = mapped_column(Date)

    # Relationship
    company: Mapped["Company"] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<KeyEvent {self.rcept_no}: {self.report_nm}>"


class FinancialNote(Base):
    """Detail table for XBRL financial notes (textual disclosures)."""

    __tablename__ = "financial_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corp_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("companies.corp_code"), index=True
    )
    rcept_no: Mapped[str] = mapped_column(String(14), index=True)
    year: Mapped[int] = mapped_column(Integer)
    report_code: Mapped[str] = mapped_column(String(5))
    concept_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    context_ref: Mapped[str] = mapped_column(String(100))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint(
            "corp_code",
            "rcept_no",
            "concept_id",
            name="unique_financial_note",
        ),
    )

    # Relationship
    company: Mapped["Company"] = relationship(back_populates="financial_notes")

    def __repr__(self) -> str:
        return (
            f"<FinancialNote {self.corp_code} {self.year} {self.report_code}: "
            f"{self.title[:50]}>"
        )


class BackfillProgress(Base):
    """Track backfill progress for resumption."""

    __tablename__ = "backfill_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corp_code: Mapped[str] = mapped_column(String(8), index=True)
    year: Mapped[int] = mapped_column(Integer)
    report_code: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20))  # 'completed', 'failed', 'skipped'
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "corp_code", "year", "report_code", name="unique_backfill_progress"
        ),
    )
