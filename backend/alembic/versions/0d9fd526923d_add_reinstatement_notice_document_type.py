"""add reinstatement notice document type

Revision ID: 0d9fd526923d
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15 18:10:45.356296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d9fd526923d'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'REINSTATEMENT_NOTICE'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
