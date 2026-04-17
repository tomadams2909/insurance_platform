"""add payment fields to quotes

Revision ID: b1c2d3e4f5a6
Revises: f3c1a8b7a256
Create Date: 2026-04-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f3c1a8b7a256'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DO $$ BEGIN CREATE TYPE paymenttype AS ENUM ('CASH', 'FINANCE'); EXCEPTION WHEN duplicate_object THEN null; END $$")
    op.add_column('quotes', sa.Column(
        'payment_type',
        sa.Enum('CASH', 'FINANCE', name='paymenttype'),
        nullable=False,
        server_default='CASH',
    ))
    op.add_column('quotes', sa.Column('finance_deposit', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('quotes', sa.Column('finance_term_months', sa.Integer(), nullable=True))
    op.add_column('quotes', sa.Column('finance_breakdown', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('quotes', 'finance_breakdown')
    op.drop_column('quotes', 'finance_term_months')
    op.drop_column('quotes', 'finance_deposit')
    op.drop_column('quotes', 'payment_type')
    op.execute("DROP TYPE IF EXISTS paymenttype")
