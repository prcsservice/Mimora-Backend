"""
Booking Service — Core business logic for instant booking
"""
import datetime
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.models import Artist, User
from app.Booking.models import Booking, BookingPackage, ArtistPackage
from app.Booking.services.travel_charge import calculate_distance, calculate_travel_charge
from app.Booking.services.redis_client import (
    set_booking_timer,
    cancel_booking_timer,
    is_booking_active,
    BOOKING_TIMER_TTL,
)
from app.Booking.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)


# ═══════════════════════ Artist Packages ═══════════════════════

def create_artist_package(db: Session, artist_id: UUID, data: dict) -> ArtistPackage:
    """Create a new package for an artist."""
    package = ArtistPackage(
        artist_id=artist_id,
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        duration_minutes=data.get("duration_minutes"),
        category=data.get("category"),
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    logger.info(f"Package created: {package.id} for artist {artist_id}")
    return package


def get_artist_packages(db: Session, artist_id: UUID, active_only: bool = True) -> list[ArtistPackage]:
    """Get all packages for an artist."""
    query = db.query(ArtistPackage).filter(ArtistPackage.artist_id == artist_id)
    if active_only:
        query = query.filter(ArtistPackage.is_active == True)
    return query.order_by(ArtistPackage.created_at.desc()).all()


def update_artist_package(db: Session, package_id: UUID, artist_id: UUID, data: dict) -> Optional[ArtistPackage]:
    """Update an existing package (only if owned by the artist)."""
    package = (
        db.query(ArtistPackage)
        .filter(ArtistPackage.id == package_id, ArtistPackage.artist_id == artist_id)
        .first()
    )
    if not package:
        return None

    for key, value in data.items():
        if value is not None:
            setattr(package, key, value)

    db.commit()
    db.refresh(package)
    return package


def delete_artist_package(db: Session, package_id: UUID, artist_id: UUID) -> bool:
    """Soft-delete a package by marking it inactive."""
    package = (
        db.query(ArtistPackage)
        .filter(ArtistPackage.id == package_id, ArtistPackage.artist_id == artist_id)
        .first()
    )
    if not package:
        return False
    package.is_active = False
    db.commit()
    return True


# ═══════════════════════ Instant Booking ═══════════════════════

async def create_instant_booking(
    db: Session,
    customer_id: UUID,
    artist_id: UUID,
    package_ids: list[UUID],
    customer_lat: float,
    customer_lng: float,
    customer_address: Optional[str] = None,
    customer_notes: Optional[str] = None,
    fallback_artist_ids: Optional[list[UUID]] = None,
) -> Booking:
    """
    Create an instant booking:
    1. Validate artist exists and is active
    2. Validate packages belong to the artist
    3. Calculate distance + travel charge
    4. Create booking + booking_packages
    5. Set Redis timer (2 min)
    6. Notify artist via WebSocket
    """
    # 1. Validate artist
    artist = db.query(Artist).filter(Artist.id == artist_id, Artist.is_active == True).first()
    if not artist:
        raise ValueError("Artist not found or inactive")

    if artist.booking_mode not in ("instant", "both"):
        raise ValueError("Artist does not accept instant bookings")

    # 2. Validate packages
    packages = (
        db.query(ArtistPackage)
        .filter(
            ArtistPackage.id.in_(package_ids),
            ArtistPackage.artist_id == artist_id,
            ArtistPackage.is_active == True,
        )
        .all()
    )

    if len(packages) != len(package_ids):
        raise ValueError("One or more packages not found or inactive")

    # 3. Calculate distance & travel charge
    artist_lat = artist.latitude or 0
    artist_lng = artist.longitude or 0

    distance_km = await calculate_distance(customer_lat, customer_lng, artist_lat, artist_lng)
    travel_charge = calculate_travel_charge(distance_km)

    # 4. Calculate totals
    total_amount = sum(float(p.price) for p in packages)
    grand_total = total_amount + travel_charge

    # Expiry time
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=BOOKING_TIMER_TTL)

    # Create booking
    booking = Booking(
        customer_id=customer_id,
        artist_id=artist_id,
        booking_type="instant",
        status="pending",
        total_amount=total_amount,
        travel_charge=travel_charge,
        grand_total=grand_total,
        customer_lat=customer_lat,
        customer_lng=customer_lng,
        customer_address=customer_address,
        artist_lat=artist_lat,
        artist_lng=artist_lng,
        distance_km=distance_km,
        expires_at=expires_at,
        fallback_artist_ids=fallback_artist_ids or [],
        current_fallback_index=0,
        customer_notes=customer_notes,
    )
    db.add(booking)
    db.flush()  # Get the auto-generated ID

    # Create booking_packages (snapshot prices)
    for pkg in packages:
        bp = BookingPackage(
            booking_id=booking.id,
            package_id=pkg.id,
            price_at_booking=float(pkg.price),
        )
        db.add(bp)

    db.commit()
    db.refresh(booking)

    # 5. Set Redis timer
    await set_booking_timer(str(booking.id))

    # 6. Notify artist via WebSocket
    await ws_manager.notify_artist(str(artist_id), {
        "type": "new_booking",
        "booking_id": str(booking.id),
        "customer_lat": customer_lat,
        "customer_lng": customer_lng,
        "distance_km": distance_km,
        "total_amount": total_amount,
        "travel_charge": travel_charge,
        "grand_total": grand_total,
        "packages": [{"name": p.name, "price": float(p.price)} for p in packages],
        "expires_at": expires_at.isoformat(),
        "customer_notes": customer_notes,
    })

    logger.info(f"Instant booking created: {booking.id} (artist={artist_id}, total=₹{grand_total})")
    return booking


async def artist_respond(
    db: Session,
    booking_id: UUID,
    artist_id: UUID,
    action: str,  # "accept" | "decline"
) -> Booking:
    """
    Artist accepts or declines a booking.
    On decline → auto-advance to the next fallback artist.
    """
    booking = (
        db.query(Booking)
        .filter(Booking.id == booking_id, Booking.artist_id == artist_id)
        .first()
    )
    if not booking:
        raise ValueError("Booking not found or you are not the assigned artist")

    if booking.status != "pending":
        raise ValueError(f"Booking is no longer pending (current: {booking.status})")

    # Check if timer is still active
    timer_active = await is_booking_active(str(booking_id))
    if not timer_active:
        raise ValueError("Booking accept window has expired")

    now = datetime.datetime.utcnow()

    if action == "accept":
        booking.status = "accepted"
        booking.accepted_at = now
        await cancel_booking_timer(str(booking_id))

        # Notify customer
        await ws_manager.notify_customer(str(booking.customer_id), {
            "type": "booking_accepted",
            "booking_id": str(booking.id),
            "artist_id": str(artist_id),
        })

        logger.info(f"Booking {booking_id} accepted by artist {artist_id}")

    elif action == "decline":
        booking.status = "declined"
        booking.declined_at = now
        await cancel_booking_timer(str(booking_id))

        # Notify customer
        await ws_manager.notify_customer(str(booking.customer_id), {
            "type": "booking_declined",
            "booking_id": str(booking.id),
            "artist_id": str(artist_id),
        })

        logger.info(f"Booking {booking_id} declined by artist {artist_id}")

        # Try next fallback artist
        await _advance_to_next_artist(db, booking)

    db.commit()
    db.refresh(booking)
    return booking


async def handle_booking_expiry(booking_id: str):
    """
    Called when the Redis TTL expires for a booking.
    Marks the booking as expired and tries the next fallback artist.
    """
    from app.Booking.database import SessionLocal
    db = SessionLocal()

    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            logger.warning(f"Expired booking not found: {booking_id}")
            return

        if booking.status != "pending":
            logger.info(f"Booking {booking_id} already resolved ({booking.status}), skipping expiry")
            return

        booking.status = "expired"
        booking.declined_at = datetime.datetime.utcnow()

        # Notify customer
        await ws_manager.notify_customer(str(booking.customer_id), {
            "type": "booking_expired",
            "booking_id": str(booking.id),
            "artist_id": str(booking.artist_id),
        })

        logger.info(f"Booking {booking_id} expired (artist {booking.artist_id} did not respond)")

        # Try next fallback artist
        await _advance_to_next_artist(db, booking)

        db.commit()
    except Exception as e:
        logger.error(f"Error handling booking expiry {booking_id}: {e}")
        db.rollback()
    finally:
        db.close()


async def _advance_to_next_artist(db: Session, booking: Booking):
    """
    Try the next artist in the fallback list.
    Creates a new booking for the next artist with the same packages.
    """
    fallback_ids = booking.fallback_artist_ids or []
    current_idx = booking.current_fallback_index or 0

    if current_idx >= len(fallback_ids):
        logger.info(f"No more fallback artists for booking {booking.id}")
        # Notify customer that no artist is available
        await ws_manager.notify_customer(str(booking.customer_id), {
            "type": "no_artists_available",
            "booking_id": str(booking.id),
            "message": "All nearby artists are unavailable. Please try again later.",
        })
        return

    next_artist_id = fallback_ids[current_idx]
    booking.current_fallback_index = current_idx + 1
    db.commit()

    # Get original package IDs from booking_packages
    original_packages = (
        db.query(BookingPackage)
        .filter(BookingPackage.booking_id == booking.id)
        .all()
    )
    package_ids = [bp.package_id for bp in original_packages]

    # Check if next artist has the same packages (they might not)
    next_artist = db.query(Artist).filter(Artist.id == next_artist_id, Artist.is_active == True).first()
    if not next_artist:
        logger.warning(f"Fallback artist {next_artist_id} not found or inactive, skipping")
        await _advance_to_next_artist(db, booking)
        return

    # Calculate new distance & travel charge for the fallback artist
    from app.Booking.services.travel_charge import calculate_distance, calculate_travel_charge

    artist_lat = next_artist.latitude or 0
    artist_lng = next_artist.longitude or 0
    distance_km = await calculate_distance(
        booking.customer_lat, booking.customer_lng,
        artist_lat, artist_lng,
    )
    travel_charge = calculate_travel_charge(distance_km)
    grand_total = float(booking.total_amount) + travel_charge
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=BOOKING_TIMER_TTL)

    # Create new booking for the fallback artist
    new_booking = Booking(
        customer_id=booking.customer_id,
        artist_id=next_artist_id,
        booking_type="instant",
        status="pending",
        total_amount=booking.total_amount,
        travel_charge=travel_charge,
        grand_total=grand_total,
        customer_lat=booking.customer_lat,
        customer_lng=booking.customer_lng,
        customer_address=booking.customer_address,
        artist_lat=artist_lat,
        artist_lng=artist_lng,
        distance_km=distance_km,
        expires_at=expires_at,
        fallback_artist_ids=fallback_ids,
        current_fallback_index=booking.current_fallback_index,
        customer_notes=booking.customer_notes,
    )
    db.add(new_booking)
    db.flush()

    # Copy package links
    for bp in original_packages:
        new_bp = BookingPackage(
            booking_id=new_booking.id,
            package_id=bp.package_id,
            price_at_booking=bp.price_at_booking,
        )
        db.add(new_bp)

    db.commit()
    db.refresh(new_booking)

    # Set timer + notify fallback artist
    await set_booking_timer(str(new_booking.id))

    # Get package names for notification
    packages = (
        db.query(ArtistPackage)
        .filter(ArtistPackage.id.in_(package_ids))
        .all()
    )

    await ws_manager.notify_artist(str(next_artist_id), {
        "type": "new_booking",
        "booking_id": str(new_booking.id),
        "customer_lat": booking.customer_lat,
        "customer_lng": booking.customer_lng,
        "distance_km": distance_km,
        "total_amount": float(booking.total_amount),
        "travel_charge": travel_charge,
        "grand_total": grand_total,
        "packages": [{"name": p.name, "price": float(p.price)} for p in packages],
        "expires_at": expires_at.isoformat(),
        "customer_notes": booking.customer_notes,
    })

    # Notify customer about fallback
    await ws_manager.notify_customer(str(booking.customer_id), {
        "type": "booking_fallback",
        "original_booking_id": str(booking.id),
        "new_booking_id": str(new_booking.id),
        "new_artist_id": str(next_artist_id),
        "message": "Searching for the next available artist...",
    })

    logger.info(f"Fallback: booking {new_booking.id} created for artist {next_artist_id}")


# ═══════════════════════ Queries ═══════════════════════

def get_booking(db: Session, booking_id: UUID) -> Optional[Booking]:
    """Get a booking by ID."""
    return db.query(Booking).filter(Booking.id == booking_id).first()


def get_customer_bookings(db: Session, customer_id: UUID, limit: int = 20, offset: int = 0) -> list[Booking]:
    """Get bookings for a customer, newest first."""
    return (
        db.query(Booking)
        .filter(Booking.customer_id == customer_id)
        .order_by(Booking.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_artist_bookings(db: Session, artist_id: UUID, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> list[Booking]:
    """Get bookings for an artist, optionally filtered by status."""
    query = db.query(Booking).filter(Booking.artist_id == artist_id)
    if status:
        query = query.filter(Booking.status == status)
    return query.order_by(Booking.created_at.desc()).offset(offset).limit(limit).all()
