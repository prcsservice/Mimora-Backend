"""
Geo-Search Service — Find nearby artists using PostGIS spatial queries
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_

from app.auth.models import Artist

logger = logging.getLogger(__name__)


def search_nearby_artists(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float = 20.0,
    booking_mode: Optional[str] = None,
    limit: int = 20,
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
            (distance_expr / 1000).label("distance_km"),  # Convert meters → km
        )
        .filter(and_(*filters))
        .order_by(distance_expr.asc())
        .limit(limit)
        .all()
    )

    artists = []
    for row in results:
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
        })

    logger.info(f"Geo-search: found {len(artists)} artists within {radius_km}km of ({latitude}, {longitude})")
    return artists
