"""Add Latest_Financials view.

Revision ID: 002_view
Revises: 001_initial
Create Date: 2026-01-17

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "002_view"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create Latest_Financials view per spec section 4.2.2
    # Shows only the most recent version of each financial entry
    op.execute("""
        CREATE VIEW latest_financials AS
        SELECT
            f.year,
            CASE f.report_code
                WHEN '11013' THEN 'Q1'
                WHEN '11012' THEN 'Q2'
                WHEN '11014' THEN 'Q3'
                WHEN '11011' THEN 'Q4/Annual'
                ELSE f.report_code
            END AS quarter,
            f.corp_code,
            c.stock_code,
            f.fs_div,
            f.account_name,
            f.account_id,
            f.amount
        FROM financial_fundamentals f
        JOIN companies c ON f.corp_code = c.corp_code
        WHERE f.version = (
            SELECT MAX(f2.version)
            FROM financial_fundamentals f2
            WHERE f2.corp_code = f.corp_code
              AND f2.year = f.year
              AND f2.report_code = f.report_code
              AND f2.fs_div = f.fs_div
              AND f2.account_id = f.account_id
        )
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS latest_financials")
