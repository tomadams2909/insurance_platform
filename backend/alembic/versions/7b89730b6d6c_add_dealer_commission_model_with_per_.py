"""add dealer commission model with per-product rate override

Revision ID: 7b89730b6d6c
Revises: abac657043a5
Create Date: 2026-04-16 14:42:33.375449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7b89730b6d6c'
down_revision: Union[str, Sequence[str], None] = 'abac657043a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# producttype already exists in the DB (created by the quotes migration)
existing_producttype = postgresql.ENUM(
    'GAP', 'VRI', 'COSMETIC', 'TYRE_ESSENTIAL', 'TYRE_PLUS', 'TLP',
    name='producttype',
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('dealer_commissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dealer_id', sa.Integer(), nullable=False),
    sa.Column('product', existing_producttype, nullable=True),
    sa.Column('commission_type', sa.Enum('PERCENTAGE', 'FLAT_FEE', name='commissiontype'), nullable=False),
    sa.Column('commission_rate', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['dealer_id'], ['dealers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dealer_commissions_id'), 'dealer_commissions', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_dealer_commissions_id'), table_name='dealer_commissions')
    op.drop_table('dealer_commissions')
    op.execute("DROP TYPE IF EXISTS commissiontype")
