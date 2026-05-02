"""extend artist_packages and artist toggle

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-23 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine.reflection import Inspector
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in Inspector.from_engine(bind).get_table_names()


def _column_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    cols = [c['name'] for c in Inspector.from_engine(bind).get_columns(table)]
    return col in cols


def upgrade() -> None:
    """
    Part A: Create Booking tables if they don't exist (artist_packages, bookings, booking_packages).
    Part B: Add Sprint 1 columns to the existing artists table.
    """

    # ── Part A-1: Create artist_packages table ──
    if not _table_exists('artist_packages'):
        op.create_table(
            'artist_packages',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('artist_id', UUID(as_uuid=True), sa.ForeignKey('artists.id'), nullable=True, index=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('price', sa.Numeric(10, 2), nullable=False),
            sa.Column('duration_minutes', sa.Integer(), nullable=True),
            sa.Column('category', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            # Sprint 1 columns (included at create time)
            sa.Column('is_template', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('module', sa.String(50), nullable=False, server_default='instant'),
            sa.Column('image_url', sa.String(500), nullable=True),
            sa.Column('service_type', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('idx_artist_packages_is_template', 'artist_packages', ['is_template'])
        op.create_index('idx_artist_packages_module', 'artist_packages', ['module'])
    else:
        # Table exists but may lack Sprint 1 columns
        op.execute("ALTER TABLE artist_packages ADD COLUMN IF NOT EXISTS is_template BOOLEAN NOT NULL DEFAULT FALSE")
        op.execute("ALTER TABLE artist_packages ADD COLUMN IF NOT EXISTS module VARCHAR(50) NOT NULL DEFAULT 'instant'")
        op.execute("ALTER TABLE artist_packages ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)")
        op.execute("ALTER TABLE artist_packages ADD COLUMN IF NOT EXISTS service_type VARCHAR(100)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_artist_packages_is_template ON artist_packages(is_template)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_artist_packages_module ON artist_packages(module)")
        op.execute("ALTER TABLE artist_packages ALTER COLUMN artist_id DROP NOT NULL")

    # ── Part A-2: Create bookings table ──
    if not _table_exists('bookings'):
        op.create_table(
            'bookings',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('customer_id', UUID(as_uuid=True), sa.ForeignKey('customer.id'), nullable=False, index=True),
            sa.Column('artist_id', UUID(as_uuid=True), sa.ForeignKey('artists.id'), nullable=False, index=True),
            sa.Column('booking_type', sa.String(), nullable=False, server_default='instant'),
            sa.Column('status', sa.String(), nullable=False, server_default='pending', index=True),
            sa.Column('total_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
            sa.Column('travel_charge', sa.Numeric(10, 2), nullable=False, server_default='0'),
            sa.Column('grand_total', sa.Numeric(10, 2), nullable=False, server_default='0'),
            sa.Column('customer_lat', sa.Float(), nullable=True),
            sa.Column('customer_lng', sa.Float(), nullable=True),
            sa.Column('customer_address', sa.Text(), nullable=True),
            sa.Column('artist_lat', sa.Float(), nullable=True),
            sa.Column('artist_lng', sa.Float(), nullable=True),
            sa.Column('distance_km', sa.Float(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('fallback_artist_ids', sa.ARRAY(UUID(as_uuid=True)), server_default='{}'),
            sa.Column('current_fallback_index', sa.Integer(), server_default='0'),
            sa.Column('customer_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.Column('declined_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        )

    # ── Part A-3: Create booking_packages join table ──
    if not _table_exists('booking_packages'):
        op.create_table(
            'booking_packages',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('booking_id', UUID(as_uuid=True), sa.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('package_id', UUID(as_uuid=True), sa.ForeignKey('artist_packages.id'), nullable=False, index=True),
            sa.Column('price_at_booking', sa.Numeric(10, 2), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # ── Part B: Add Sprint 1 columns to existing artists table ──

    if not _column_exists('artists', 'instant_toggle'):
        op.execute("ALTER TABLE artists ADD COLUMN instant_toggle BOOLEAN NOT NULL DEFAULT FALSE")

    if not _column_exists('artists', 'gps_point'):
        op.execute("ALTER TABLE artists ADD COLUMN gps_point geography(POINT, 4326)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_artists_gps_point ON artists USING GIST(gps_point)")

    if not _column_exists('artists', 'studio_point'):
        op.execute("ALTER TABLE artists ADD COLUMN studio_point geography(POINT, 4326)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_artists_studio_point ON artists USING GIST(studio_point)")

    if not _column_exists('artists', 'artist_type'):
        op.execute("ALTER TABLE artists ADD COLUMN artist_type VARCHAR(50) DEFAULT 'both'")


def downgrade() -> None:
    """Drop Booking tables and Sprint 1 columns from artists."""
    op.execute("DROP TABLE IF EXISTS booking_packages CASCADE")
    op.execute("DROP TABLE IF EXISTS bookings CASCADE")
    op.execute("DROP TABLE IF EXISTS artist_packages CASCADE")

    op.execute("ALTER TABLE artists DROP COLUMN IF EXISTS artist_type")
    op.execute("ALTER TABLE artists DROP COLUMN IF EXISTS studio_point")
    op.execute("ALTER TABLE artists DROP COLUMN IF EXISTS gps_point")
    op.execute("ALTER TABLE artists DROP COLUMN IF EXISTS instant_toggle")
