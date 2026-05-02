"""
Booking Microservice — Database Models
"""
import datetime
import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Integer,
    ForeignKey,
    ARRAY,
    DateTime,
    Text,
    Numeric,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.Booking.database import Base


# ─────────────────────────── Artist Package ───────────────────────────
class ArtistPackage(Base):
    """A service package offered by an artist (e.g. 'Bridal HD Makeup — ₹5000')"""
    __tablename__ = "artist_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id"), nullable=True, index=True)

    name = Column(String, nullable=False)              # "Bridal HD Makeup"
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)     # ₹5000.00
    duration_minutes = Column(Integer, nullable=True)   # Approx time in mins
    category = Column(String, nullable=True)            # "bridal" | "party" | "editorial"
    is_active = Column(Boolean, default=True)

    # Sprint 1 — new columns
    is_template = Column(Boolean, nullable=False, default=False)
    module = Column(String(50), nullable=False, default="instant")  # "instant" | "flexi" | "workshop"
    image_url = Column(String(500), nullable=True)
    service_type = Column(String(100), nullable=True)  # "makeup" | "nail" | "hairstyle" | "mehendi" | "saree_draping" | "saree_pleating"

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    booking_packages = relationship("BookingPackage", back_populates="package")

    def __repr__(self):
        return f"<ArtistPackage(id={self.id}, name={self.name}, price={self.price})>"


# ─────────────────────────── Booking ───────────────────────────
class Booking(Base):
    """Core booking record"""
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Participants
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id"), nullable=False, index=True)
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id"), nullable=False, index=True)

    # Booking type & status
    booking_type = Column(String, nullable=False, default="instant")  # "instant" | "flexi"
    status = Column(String, nullable=False, default="pending", index=True)
    # Status lifecycle: pending → accepted | declined | expired | cancelled | completed

    # Pricing
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)    # Sum of package prices
    travel_charge = Column(Numeric(10, 2), nullable=False, default=0)
    grand_total = Column(Numeric(10, 2), nullable=False, default=0)     # total_amount + travel_charge

    # Location — Customer
    customer_lat = Column(Float, nullable=True)
    customer_lng = Column(Float, nullable=True)
    customer_address = Column(Text, nullable=True)

    # Location — Artist (snapshot at booking time)
    artist_lat = Column(Float, nullable=True)
    artist_lng = Column(Float, nullable=True)

    # Distance
    distance_km = Column(Float, nullable=True)

    # Timer / Fallback
    expires_at = Column(DateTime, nullable=True)       # When current accept window ends
    fallback_artist_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)  # Ordered next-best artists
    current_fallback_index = Column(Integer, default=0)

    # Notes
    customer_notes = Column(Text, nullable=True)

    # Sprint 3 — customer contact snapshot at create time. Lets the artist see
    # who's calling without joining customer table, and survives later edits.
    customer_name = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)

    # Sprint 3 — cancellation
    cancelled_by = Column(String(20), nullable=True)        # "customer" | "artist"
    cancellation_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Relationships
    booking_packages = relationship("BookingPackage", back_populates="booking", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Booking(id={self.id}, status={self.status}, artist={self.artist_id})>"


# ─────────────────────────── Booking ↔ Package (M2M Join) ───────────────────────────
class BookingPackage(Base):
    """Links a booking to the packages selected by the customer"""
    __tablename__ = "booking_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    package_id = Column(UUID(as_uuid=True), ForeignKey("artist_packages.id"), nullable=False, index=True)

    # Snapshot price at booking time (package price may change later)
    price_at_booking = Column(Numeric(10, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    booking = relationship("Booking", back_populates="booking_packages")
    package = relationship("ArtistPackage", back_populates="booking_packages")

    def __repr__(self):
        return f"<BookingPackage(booking={self.booking_id}, package={self.package_id})>"
