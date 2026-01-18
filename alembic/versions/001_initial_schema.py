"""Initial schema - companies, financial_fundamentals, key_events, backfill_progress.

Revision ID: 001_initial
Revises:
Create Date: 2026-01-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Companies (master table)
    op.create_table(
        "companies",
        sa.Column("corp_code", sa.String(8), primary_key=True),
        sa.Column("stock_code", sa.String(6), unique=True, nullable=True),
        sa.Column("corp_name", sa.String(255), nullable=False),
        sa.Column("is_priority", sa.Boolean(), default=False, nullable=False),
        sa.Column("listing_date", sa.Date(), nullable=True),
        sa.Column("delisted_date", sa.Date(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column(
            "earliest_data_year",
            sa.Integer(),
            nullable=True,
            comment="Earliest year with available DART data",
        ),
    )

    # Financial Fundamentals (detail table)
    op.create_table(
        "financial_fundamentals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "corp_code",
            sa.String(8),
            sa.ForeignKey("companies.corp_code"),
            nullable=False,
            index=True,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("report_code", sa.String(5), nullable=False),
        sa.Column("fs_div", sa.String(3), nullable=False),  # CFS or OFS
        sa.Column("account_id", sa.String(20), nullable=False),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "corp_code",
            "year",
            "report_code",
            "fs_div",
            "account_id",
            "version",
            name="unique_financial_entry",
        ),
    )

    # Key Events (detail table)
    op.create_table(
        "key_events",
        sa.Column("rcept_no", sa.String(14), primary_key=True),
        sa.Column(
            "corp_code",
            sa.String(8),
            sa.ForeignKey("companies.corp_code"),
            nullable=False,
            index=True,
        ),
        sa.Column("report_nm", sa.String(255), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
    )

    # Backfill Progress (checkpoint table)
    op.create_table(
        "backfill_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("corp_code", sa.String(8), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("report_code", sa.String(5), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),  # completed, failed, skipped
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "corp_code", "year", "report_code", name="unique_backfill_progress"
        ),
    )


def downgrade() -> None:
    op.drop_table("backfill_progress")
    op.drop_table("key_events")
    op.drop_table("financial_fundamentals")
    op.drop_table("companies")
