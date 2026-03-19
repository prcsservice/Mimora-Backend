"""
Booking Routes — API endpoints for instant booking, geo-search, and package management
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.Booking.database import get_db
from app.auth.utils.current_user import get_current_user, get_current_artist
from app.auth.models import User, Artist
from app.Booking.schemas import (
    GeoSearchRequest,
    GeoSearchResponse,
    GeoSearchArtistResult,
    InstantBookingRequest,
    BookingResponse,
    BookingAcceptDecline,
    BookingListResponse,
    BookingPackageDetail,
    ArtistPackageCreate,
    ArtistPackageUpdate,
    ArtistPackageResponse,
)
from app.Booking.services.geo_search import search_nearby_artists
from app.Booking.services.booking_service import (
    create_instant_booking,
    artist_respond,
    get_booking,
    get_customer_bookings,
    get_artist_bookings,
    create_artist_package,
    get_artist_packages,
    update_artist_package,
    delete_artist_package,
)
from app.Booking.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/booking", tags=["Booking"])


# ═══════════════════════ Geo-Search ═══════════════════════

@router.post("/search/nearby", response_model=GeoSearchResponse)
def search_nearby(payload: GeoSearchRequest, db: Session = Depends(get_db)):
    """
    Search for nearby artists based on customer's location.
    Uses PostGIS spatial queries on the artists table.
    """
    artists = search_nearby_artists(
        db=db,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
        booking_mode=payload.booking_mode,
        limit=payload.limit,
    )
    return GeoSearchResponse(
        artists=[GeoSearchArtistResult(**a) for a in artists],
        total=len(artists),
    )


# ═══════════════════════ Instant Booking ═══════════════════════

@router.post("/instant", response_model=BookingResponse)
async def create_booking(
    payload: InstantBookingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create an instant booking.
    Notifies the artist via WebSocket and starts a 2-minute accept timer.
    """
    try:
        booking = await create_instant_booking(
            db=db,
            customer_id=current_user.id,
            artist_id=payload.artist_id,
            package_ids=payload.package_ids,
            customer_lat=payload.latitude,
            customer_lng=payload.longitude,
            customer_address=payload.address,
            customer_notes=payload.customer_notes,
            fallback_artist_ids=payload.fallback_artist_ids,
        )
        return _booking_to_response(booking, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{booking_id}/respond", response_model=BookingResponse)
async def respond_to_booking(
    booking_id: UUID,
    payload: BookingAcceptDecline,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """
    Artist accepts or declines a booking.
    On decline, the system automatically tries the next fallback artist.
    """
    try:
        booking = await artist_respond(
            db=db,
            booking_id=booking_id,
            artist_id=current_artist.id,
            action=payload.action,
        )
        return _booking_to_response(booking, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════ Booking Queries ═══════════════════════

@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_detail(
    booking_id: UUID,
    db: Session = Depends(get_db),
):
    """Get a booking by ID."""
    booking = get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_to_response(booking, db)


@router.get("/customer/list", response_model=BookingListResponse)
def list_customer_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """List bookings for the current customer."""
    bookings = get_customer_bookings(db, current_user.id, limit=limit, offset=offset)
    return BookingListResponse(
        bookings=[_booking_to_response(b, db) for b in bookings],
        total=len(bookings),
    )


@router.get("/artist/list", response_model=BookingListResponse)
def list_artist_bookings(
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
    status: str = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """List bookings for the current artist, optionally filtered by status."""
    bookings = get_artist_bookings(db, current_artist.id, status=status, limit=limit, offset=offset)
    return BookingListResponse(
        bookings=[_booking_to_response(b, db) for b in bookings],
        total=len(bookings),
    )


# ═══════════════════════ Artist Packages ═══════════════════════

@router.post("/artist/packages", response_model=ArtistPackageResponse)
def create_package(
    payload: ArtistPackageCreate,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Create a new package for the authenticated artist."""
    package = create_artist_package(db, current_artist.id, payload.model_dump())
    return package


@router.get("/artist/{artist_id}/packages", response_model=list[ArtistPackageResponse])
def list_packages(
    artist_id: UUID,
    db: Session = Depends(get_db),
):
    """List active packages for an artist (public endpoint)."""
    return get_artist_packages(db, artist_id)


@router.put("/artist/packages/{package_id}", response_model=ArtistPackageResponse)
def update_package(
    package_id: UUID,
    payload: ArtistPackageUpdate,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Update an existing package (only the owning artist can update)."""
    package = update_artist_package(
        db, package_id, current_artist.id,
        payload.model_dump(exclude_unset=True),
    )
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return package


@router.delete("/artist/packages/{package_id}")
def remove_package(
    package_id: UUID,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Soft-delete a package (marks as inactive)."""
    success = delete_artist_package(db, package_id, current_artist.id)
    if not success:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"detail": "Package deactivated"}


# ═══════════════════════ WebSocket Endpoints ═══════════════════════

@router.websocket("/ws/artist/{artist_id}")
async def websocket_artist(websocket: WebSocket, artist_id: str):
    """
    WebSocket connection for artists to receive real-time booking notifications.
    Artists connect here and receive JSON messages when they get new bookings.
    """
    await ws_manager.connect_artist(artist_id, websocket)
    try:
        while True:
            # Keep connection alive — listen for pings/messages
            data = await websocket.receive_text()
            # Artists can send heartbeat pings
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_artist(artist_id)
        logger.info(f"Artist {artist_id} WebSocket disconnected")


@router.websocket("/ws/customer/{customer_id}")
async def websocket_customer(websocket: WebSocket, customer_id: str):
    """
    WebSocket connection for customers to receive real-time booking updates.
    Customers connect here to get status updates (accepted, declined, expired, fallback).
    """
    await ws_manager.connect_customer(customer_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_customer(customer_id)
        logger.info(f"Customer {customer_id} WebSocket disconnected")


# ═══════════════════════ Helper ═══════════════════════

def _booking_to_response(booking, db: Session) -> BookingResponse:
    """Convert a Booking ORM object to a BookingResponse schema."""
    from app.Booking.models import BookingPackage, ArtistPackage

    # Get package details
    packages = (
        db.query(BookingPackage, ArtistPackage)
        .join(ArtistPackage, BookingPackage.package_id == ArtistPackage.id)
        .filter(BookingPackage.booking_id == booking.id)
        .all()
    )

    package_details = [
        BookingPackageDetail(
            package_id=bp.package_id,
            name=pkg.name,
            price=float(bp.price_at_booking),
        )
        for bp, pkg in packages
    ]

    return BookingResponse(
        id=booking.id,
        customer_id=booking.customer_id,
        artist_id=booking.artist_id,
        booking_type=booking.booking_type,
        status=booking.status,
        total_amount=float(booking.total_amount),
        travel_charge=float(booking.travel_charge),
        grand_total=float(booking.grand_total),
        customer_lat=booking.customer_lat,
        customer_lng=booking.customer_lng,
        customer_address=booking.customer_address,
        artist_lat=booking.artist_lat,
        artist_lng=booking.artist_lng,
        distance_km=booking.distance_km,
        expires_at=booking.expires_at,
        customer_notes=booking.customer_notes,
        packages=package_details,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        accepted_at=booking.accepted_at,
        declined_at=booking.declined_at,
        completed_at=booking.completed_at,
        cancelled_at=booking.cancelled_at,
    )
