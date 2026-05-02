"""
Geo-Search Service — Find nearby artists using PostGIS spatial queries
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_

from app.auth.models import Artist
from app.Booking.models import ArtistPackage

logger = logging.getLogger(__name__)


def search_nearby_artists(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float = 20.0,
    booking_mode: Optional[str] = None,
    limit: int = 20,
    # Sprint 2 — Discovery filters
    instant_only: bool = True,
    location_type: Optional[str] = None,
    artist_type: Optional[str] = None,
    service_type: Optional[str] = None,
    min_rating: Optional[float] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
) -> list[dict]:
    """
    Find artists within `radius_km` of the given (lat, lng) using PostGIS.

    Uses ST_DWithin for indexed spatial filtering and ST_Distance for
    accurate distance calculation. Both operate on the geography column.

    Returns a list of dicts with artist info + distance_km, ordered by nearest.
    """
    # Create a geography point from customer coordinates
    customer_point = func.ST_SetSRID(
        func.ST_MakePoint(longitude, latitude),  # Note: PostGIS uses (lng, lat) order
        4326
    )

    # Distance in meters (geography type returns meters by default)
    distance_expr = func.ST_Distance(
        Artist.location,
        customer_point
    )

    # Build filters
    filters = [
        Artist.is_active == True,
        Artist.profile_completed == True,
        Artist.location.isnot(None),
        # ST_DWithin for indexed spatial filtering (radius in meters)
        func.ST_DWithin(Artist.location, customer_point, radius_km * 1000),
    ]

    # Filter by booking mode if specified
    if booking_mode:
        filters.append(
            Artist.booking_mode.in_([booking_mode, "both"])
        )
    else:
        # Default: only artists who accept instant or both
        filters.append(
            Artist.booking_mode.in_(["instant", "both"])
        )

    # ── Sprint 2 filters ──

    # Filter 1: instant_toggle must be true (unless caller explicitly sets instant_only=False)
    if instant_only:
        filters.append(Artist.instant_toggle == True)

    # Filter 2: artist_type filter
    if artist_type:
        filters.append(Artist.artist_type == artist_type)
    elif location_type == "studio":
        # Studio visit: only show studio_only and both artists
        filters.append(Artist.artist_type.in_(["studio_only", "both"]))
    elif location_type == "client":
        # Artist comes to customer: only show client_only and both artists
        filters.append(Artist.artist_type.in_(["client_only", "both"]))

    # Filter 3: service_type — only show artists who have a package with this service_type
    if service_type:
        artist_ids_with_service = db.query(ArtistPackage.artist_id).filter(
            ArtistPackage.service_type == service_type,
            ArtistPackage.is_active == True,
            ArtistPackage.is_template == False
        ).subquery()
        filters.append(Artist.id.in_(artist_ids_with_service))

    # Filter 4: minimum rating
    if min_rating:
        filters.append(Artist.rating >= min_rating)

    # Filter 5: price range — filter by artist's package prices
    if price_min or price_max:
        pkg_query = db.query(ArtistPackage.artist_id).filter(
            ArtistPackage.is_active == True,
            ArtistPackage.is_template == False
        )
        if price_min:
            pkg_query = pkg_query.filter(ArtistPackage.price >= price_min)
        if price_max:
            pkg_query = pkg_query.filter(ArtistPackage.price <= price_max)
        artist_ids_in_range = pkg_query.subquery()
        filters.append(Artist.id.in_(artist_ids_in_range))

    # Query
    results = (
        db.query(
            Artist.id,
            Artist.name,
            Artist.username,
            Artist.profile_pic_url,
            Artist.profession,
            Artist.experience,
            Artist.rating,
            Artist.total_reviews,
            Artist.total_bookings,
            Artist.latitude,
            Artist.longitude,
            Artist.booking_mode,
            Artist.skills,
            Artist.artist_type,
            Artist.instant_toggle,
            Artist.city,
            (distance_expr / 1000).label("distance_km"),  # Convert meters → km
        )
        .filter(and_(*filters))
        .order_by(distance_expr.asc())
        .limit(limit)
        .all()
    )

    artists = []
    for row in results:
        # Fetch top 3 packages for this artist (for card previews)
        packages = db.query(ArtistPackage).filter(
            ArtistPackage.artist_id == row.id,
            ArtistPackage.is_active == True,
            ArtistPackage.is_template == False
        ).limit(3).all()

        packages_preview = [
            {
                "id": str(p.id),
                "name": p.name,
                "price": float(p.price),
                "image_url": p.image_url,
                "duration_minutes": p.duration_minutes,
            }
            for p in packages
        ]

        artists.append({
            "id": row.id,
            "name": row.name,
            "username": row.username,
            "profile_pic_url": row.profile_pic_url,
            "profession": row.profession,
            "experience": row.experience,
            "rating": float(row.rating) if row.rating else 0.0,
            "total_reviews": row.total_reviews or 0,
            "total_bookings": row.total_bookings or 0,
            "distance_km": round(row.distance_km, 2) if row.distance_km else 0.0,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "booking_mode": row.booking_mode,
            "skills": row.skills,
            "artist_type": row.artist_type,
            "instant_toggle": row.instant_toggle or False,
            "city": row.city,
            "packages_preview": packages_preview,
        })

    logger.info(f"Geo-search: found {len(artists)} artists within {radius_km}km of ({latitude}, {longitude})")
    return artists
