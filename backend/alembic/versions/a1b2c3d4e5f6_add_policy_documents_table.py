"""add policy documents table

Revision ID: a1b2c3d4e5f6
Revises: d3e73b81c75b
Create Date: 2026-04-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd3e73b81c75b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'policy_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.Enum('POLICY_SCHEDULE', 'ENDORSEMENT_CERTIFICATE', 'CANCELLATION_NOTICE', 'REINSTATEMENT_NOTICE', name='documenttype'), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_policy_documents_id'), 'policy_documents', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_policy_documents_id'), table_name='policy_documents')
    op.drop_table('policy_documents')
    op.execute('DROP TYPE IF EXISTS documenttype')
