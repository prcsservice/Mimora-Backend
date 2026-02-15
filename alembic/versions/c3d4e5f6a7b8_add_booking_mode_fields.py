"""add booking mode fields to artists

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-15 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add booking preference columns to artists table."""
    columns_to_add = [
        ("booking_mode", "VARCHAR", True),
        ("skills", "VARCHAR[]", True),
        ("event_types", "VARCHAR[]", True),
        ("service_location", "VARCHAR", True),
        ("travel_willingness", "VARCHAR[]", True),
        ("studio_address", "TEXT", True),
        ("working_hours", "TEXT", True),
    ]

    for col_name, col_type, nullable in columns_to_add:
        op.execute(
            f"ALTER TABLE artists ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
        )


def downgrade() -> None:
    """Remove booking preference columns from artists table."""
    columns_to_drop = [
        "booking_mode",
        "skills",
        "event_types",
        "service_location",
        "travel_willingness",
        "studio_address",
        "working_hours",
    ]

    for col_name in columns_to_drop:
        op.drop_column('artists', col_name)
