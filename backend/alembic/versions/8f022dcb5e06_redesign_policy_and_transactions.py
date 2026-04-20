"""redesign_policy_and_transactions

Revision ID: 8f022dcb5e06
Revises: 
Create Date: 2026-04-19 15:51:15.367280

"""
from typing import Sequence, Union

from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = '8f022dcb5e06'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
