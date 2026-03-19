"""
Travel Charge Calculator — Haversine or Google Maps Distance Matrix
"""
import os
import math
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Config from env
TRAVEL_CHARGE_MODE = os.getenv("TRAVEL_CHARGE_MODE", "haversine")  # "haversine" | "google_maps"
FREE_KM = float(os.getenv("FREE_KM", "5"))                         # First N km are free
RATE_PER_KM = float(os.getenv("RATE_PER_KM", "10"))               # ₹ per km after free distance
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points (in km)
    using the Haversine formula.
    """
    R = 6371  # Earth's radius in km

    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def google_maps_distance(
    lat1: float, lng1: float,
    lat2: float, lng2: float,
) -> Optional[float]:
    """
    Get driving distance (in km) using Google Maps Distance Matrix API.
    Returns None on failure.
    """
    if not GOOGLE_MAPS_API_KEY:
        logger.warning("GOOGLE_MAPS_API_KEY not set, falling back to haversine")
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={
                    "origins": f"{lat1},{lng1}",
                    "destinations": f"{lat2},{lng2}",
                    "key": GOOGLE_MAPS_API_KEY,
                    "units": "metric",
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

            if data["status"] != "OK":
                logger.error(f"Google Maps API error: {data['status']}")
                return None

            element = data["rows"][0]["elements"][0]
            if element["status"] != "OK":
                logger.error(f"Google Maps element error: {element['status']}")
                return None

            distance_meters = element["distance"]["value"]
            return distance_meters / 1000  # Convert to km

    except Exception as e:
        logger.error(f"Google Maps Distance Matrix API failed: {e}")
        return None


async def calculate_distance(
    customer_lat: float, customer_lng: float,
    artist_lat: float, artist_lng: float,
) -> float:
    """
    Calculate distance between customer and artist.
    Uses Google Maps if configured, otherwise falls back to haversine.
    """
    if TRAVEL_CHARGE_MODE == "google_maps":
        distance = await google_maps_distance(
            customer_lat, customer_lng, artist_lat, artist_lng
        )
        if distance is not None:
            return round(distance, 2)

    # Fallback to haversine
    return round(haversine_distance(customer_lat, customer_lng, artist_lat, artist_lng), 2)


def calculate_travel_charge(distance_km: float) -> float:
    """
    Calculate travel charge based on distance.
    Formula: max(0, distance_km - FREE_KM) × RATE_PER_KM
    """
    chargeable_km = max(0, distance_km - FREE_KM)
    charge = chargeable_km * RATE_PER_KM
    return round(charge, 2)
