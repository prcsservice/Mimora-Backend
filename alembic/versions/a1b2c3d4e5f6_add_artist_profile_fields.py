"""add artist profile fields

Revision ID: a1b2c3d4e5f6
Revises: 82aa7982c6ac
Create Date: 2026-02-14 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '82aa7982c6ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to artists table
    op.add_column('artists', sa.Column('profile_pic_url', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('how_did_you_learn', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('certificate_url', sa.String(), nullable=True))
    op.add_column('artists', sa.Column('profile_completed', sa.Boolean(), nullable=False, server_default='false'))

    # Make city and address nullable (they were NOT NULL before)
    op.alter_column('artists', 'city', existing_type=sa.String(), nullable=True)
    op.alter_column('artists', 'address', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Revert city and address to NOT NULL
    op.alter_column('artists', 'address', existing_type=sa.String(), nullable=False)
    op.alter_column('artists', 'city', existing_type=sa.String(), nullable=False)

    # Drop new columns
    op.drop_column('artists', 'profile_completed')
    op.drop_column('artists', 'certificate_url')
    op.drop_column('artists', 'how_did_you_learn')
    op.drop_column('artists', 'profile_pic_url')
