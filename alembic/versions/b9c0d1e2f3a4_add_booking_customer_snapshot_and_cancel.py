"""add booking customer snapshot + cancellation columns

Revision ID: b9c0d1e2f3a4
Revises: a8bc64c28291
Create Date: 2026-05-02 18:00:00.000000

Adds columns to `bookings`:
  - customer_name      VARCHAR  (snapshot at create time)
  - customer_phone     VARCHAR
  - cancelled_by       VARCHAR(20)  ("customer" | "artist")
  - cancellation_reason TEXT
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, None] = 'a8bc64c28291'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c['name'] for c in Inspector.from_engine(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _column_exists('bookings', 'customer_name'):
        op.add_column('bookings', sa.Column('customer_name', sa.String(), nullable=True))
    if not _column_exists('bookings', 'customer_phone'):
        op.add_column('bookings', sa.Column('customer_phone', sa.String(), nullable=True))
    if not _column_exists('bookings', 'cancelled_by'):
        op.add_column('bookings', sa.Column('cancelled_by', sa.String(length=20), nullable=True))
    if not _column_exists('bookings', 'cancellation_reason'):
        op.add_column('bookings', sa.Column('cancellation_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists('bookings', 'cancellation_reason'):
        op.drop_column('bookings', 'cancellation_reason')
    if _column_exists('bookings', 'cancelled_by'):
        op.drop_column('bookings', 'cancelled_by')
    if _column_exists('bookings', 'customer_phone'):
        op.drop_column('bookings', 'customer_phone')
    if _column_exists('bookings', 'customer_name'):
        op.drop_column('bookings', 'customer_name')
