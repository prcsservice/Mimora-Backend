"""sync artist table columns with model

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-14 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add all missing columns to artists table using IF NOT EXISTS.
    
    This is safe to run multiple times — it won't fail if columns already exist.
    """
    # Use raw SQL with IF NOT EXISTS for safety
    columns_to_add = [
        # Auth
        ("firebase_uid", "VARCHAR", True),
        ("provider", "VARCHAR", True),
        # Profile
        ("name", "VARCHAR", True),
        ("username", "VARCHAR", True),
        ("email", "VARCHAR", True),
        ("phone_number", "VARCHAR", True),
        ("birthdate", "TIMESTAMP", True),
        ("gender", "VARCHAR", True),
        ("bio", "TEXT", True),
        ("profile_pic_url", "VARCHAR", True),
        # Professional
        ("profession", "VARCHAR[]", True),
        ("experience", "VARCHAR", True),
        ("how_did_you_learn", "VARCHAR", True),
        ("certificate_url", "VARCHAR", True),
        # Location
        ("city", "VARCHAR", True),
        ("address", "VARCHAR", True),
        ("flat_building", "VARCHAR", True),
        ("street_area", "VARCHAR", True),
        ("landmark", "VARCHAR", True),
        ("pincode", "VARCHAR", True),
        ("state", "VARCHAR", True),
        ("latitude", "DOUBLE PRECISION", True),
        ("longitude", "DOUBLE PRECISION", True),
        ("travel_radius", "INTEGER", True),
        # KYC
        ("kyc_verified", "BOOLEAN", True),
        ("bank_verified", "BOOLEAN", True),
        ("kyc_id", "VARCHAR", True),
        # Portfolio
        ("portfolio", "VARCHAR[]", True),
        # Stats
        ("rating", "DOUBLE PRECISION", True),
        ("total_reviews", "INTEGER", True),
        ("total_bookings", "INTEGER", True),
        # Account
        ("is_active", "BOOLEAN", True),
        ("profile_completed", "BOOLEAN", True),
        # Timestamps
        ("created_at", "TIMESTAMP", True),
        ("updated_at", "TIMESTAMP", True),
    ]
    
    for col_name, col_type, nullable in columns_to_add:
        op.execute(
            f"ALTER TABLE artists ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
        )
    
    # Set defaults for boolean columns that should have them
    op.execute("UPDATE artists SET kyc_verified = false WHERE kyc_verified IS NULL")
    op.execute("UPDATE artists SET bank_verified = false WHERE bank_verified IS NULL")
    op.execute("UPDATE artists SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE artists SET profile_completed = false WHERE profile_completed IS NULL")
    op.execute("UPDATE artists SET rating = 0.0 WHERE rating IS NULL")
    op.execute("UPDATE artists SET total_reviews = 0 WHERE total_reviews IS NULL")
    op.execute("UPDATE artists SET total_bookings = 0 WHERE total_bookings IS NULL")
    op.execute("UPDATE artists SET travel_radius = 10 WHERE travel_radius IS NULL")
    op.execute("UPDATE artists SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE artists SET updated_at = NOW() WHERE updated_at IS NULL")
    
    # Add unique indexes if they don't exist
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_artists_firebase_uid 
        ON artists (firebase_uid) WHERE firebase_uid IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_artists_username 
        ON artists (username) WHERE username IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_artists_email 
        ON artists (email) WHERE email IS NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_artists_phone_number 
        ON artists (phone_number) WHERE phone_number IS NOT NULL
    """)


def downgrade() -> None:
    # We don't drop columns on downgrade since we don't know
    # which ones existed before this migration
    pass
