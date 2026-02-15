"""Add bank details fields to artists table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add bank detail columns to artists table."""
    op.add_column('artists', sa.Column('bank_account_name', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('bank_account_number', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('bank_name', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('bank_ifsc', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('upi_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove bank detail columns from artists table."""
    op.drop_column('artists', 'upi_id')
    op.drop_column('artists', 'bank_ifsc')
    op.drop_column('artists', 'bank_name')
    op.drop_column('artists', 'bank_account_number')
    op.drop_column('artists', 'bank_account_name')
