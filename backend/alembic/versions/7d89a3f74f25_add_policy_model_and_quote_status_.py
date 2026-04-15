"""add policy model and quote status extensions

Revision ID: 7d89a3f74f25
Revises: 29909565d01c
Create Date: 2026-04-10 21:46:57.219463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7d89a3f74f25'
down_revision: Union[str, Sequence[str], None] = '29909565d01c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reference existing enum — do not recreate
existing_producttype = postgresql.ENUM(
    'GAP', 'VRI', 'COSMETIC', 'TYRE_ESSENTIAL', 'TYRE_PLUS', 'TLP',
    name='producttype',
    create_type=False,
)


def upgrade() -> None:
    op.execute("ALTER TYPE quotestatus ADD VALUE IF NOT EXISTS 'NOT_TAKEN_UP'")
    op.execute("ALTER TYPE quotestatus ADD VALUE IF NOT EXISTS 'BOUND'")
    op.create_table(
        'policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('product', existing_producttype, nullable=False),
        sa.Column('status', sa.Enum('BOUND', 'ISSUED', 'CANCELLED', 'REINSTATED', name='policystatus'), nullable=False),
        sa.Column('policy_number', sa.String(), nullable=False),
        sa.Column('inception_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=False),
        sa.Column('premium', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('current_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quote_id'),
    )
    op.create_index(op.f('ix_policies_id'), 'policies', ['id'], unique=False)
    op.create_index(op.f('ix_policies_policy_number'), 'policies', ['policy_number'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_policies_policy_number'), table_name='policies')
    op.drop_index(op.f('ix_policies_id'), table_name='policies')
    op.drop_table('policies')
    op.execute("DROP TYPE IF EXISTS policystatus")
