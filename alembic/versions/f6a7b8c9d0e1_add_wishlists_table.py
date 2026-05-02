"""add wishlists table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine.reflection import Inspector


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in Inspector.from_engine(bind).get_table_names()


def upgrade() -> None:
    if not _table_exists('wishlists'):
        op.create_table(
            'wishlists',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column(
                'customer_id',
                UUID(as_uuid=True),
                sa.ForeignKey('customer.id', ondelete='CASCADE'),
                nullable=False,
                index=True,
            ),
            sa.Column(
                'artist_id',
                UUID(as_uuid=True),
                sa.ForeignKey('artists.id', ondelete='CASCADE'),
                nullable=False,
                index=True,
            ),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('customer_id', 'artist_id', name='uq_wishlists_customer_artist'),
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wishlists CASCADE")
