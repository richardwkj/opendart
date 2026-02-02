"""create_financial_indicators

Revision ID: 003_indicators
Revises: 1af33ea2791c
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_indicators'
down_revision: Union[str, Sequence[str], None] = '1af33ea2791c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create financial_indicators and indicator_backfill_progress tables."""
    # Create financial_indicators table
    op.create_table(
        'financial_indicators',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('corp_code', sa.String(length=8), nullable=False),
        sa.Column('stock_code', sa.String(length=6), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('report_code', sa.String(length=5), nullable=False),
        sa.Column('settlement_date', sa.Date(), nullable=True),
        sa.Column('idx_cl_code', sa.String(length=7), nullable=False),
        sa.Column('idx_cl_name', sa.String(length=50), nullable=False),
        sa.Column('idx_code', sa.String(length=10), nullable=False),
        sa.Column('idx_name', sa.String(length=100), nullable=False),
        sa.Column('idx_value', sa.String(length=50), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['corp_code'], ['companies.corp_code']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'corp_code', 'year', 'report_code', 'idx_code',
            name='unique_financial_indicator'
        )
    )
    op.create_index(
        op.f('ix_financial_indicators_corp_code'),
        'financial_indicators',
        ['corp_code'],
        unique=False
    )

    # Create indicator_backfill_progress table
    op.create_table(
        'indicator_backfill_progress',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('corp_code', sa.String(length=8), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('report_code', sa.String(length=5), nullable=False),
        sa.Column('idx_cl_code', sa.String(length=7), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'corp_code', 'year', 'report_code', 'idx_cl_code',
            name='unique_indicator_backfill_progress'
        )
    )
    op.create_index(
        op.f('ix_indicator_backfill_progress_corp_code'),
        'indicator_backfill_progress',
        ['corp_code'],
        unique=False
    )


def downgrade() -> None:
    """Drop financial_indicators and indicator_backfill_progress tables."""
    op.drop_index(
        op.f('ix_indicator_backfill_progress_corp_code'),
        table_name='indicator_backfill_progress'
    )
    op.drop_table('indicator_backfill_progress')

    op.drop_index(
        op.f('ix_financial_indicators_corp_code'),
        table_name='financial_indicators'
    )
    op.drop_table('financial_indicators')
