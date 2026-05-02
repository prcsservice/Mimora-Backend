"""
Booking Routes — API endpoints for instant booking, geo-search, and package management
"""
import datetime
import logging
import uuid as uuid_lib
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.Booking.database import get_db
from app.auth.utils.current_user import get_current_user, get_current_artist
from app.auth.utils.current_actor import get_current_actor
from app.auth.firebase import verify_firebase_token
from app.auth.models import User, Artist
from app.Booking.models import Booking
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
    BookingCancelRequest,
    BookingDetailResponse,
    ArtistMini,
    CustomerMini,
    ALLOWED_BOOKING_STATUSES,
)
from app.Booking.services.geo_search import search_nearby_artists
from app.Booking.services.booking_service import (
    create_instant_booking,
    artist_respond,
    get_booking,
    get_customer_bookings,
    get_artist_bookings,
    get_active_booking_for_artist,
    get_active_booking_for_customer,
    create_artist_package,
    get_artist_packages,
    update_artist_package,
    delete_artist_package,
)
from app.Booking.services.redis_client import cancel_booking_timer
from app.Booking.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/booking", tags=["Booking"])


# ═══════════════════════ Geo-Search ═══════════════════════

@router.post("/search/nearby", response_model=GeoSearchResponse)
def search_nearby(payload: GeoSearchRequest, db: Session = Depends(get_db)):
    """
    Search for nearby artists based on customer's location.
    Uses PostGIS spatial queries on the artists table.
    Supports Sprint 2 filters: instant_only, artist_type, service_type, rating, price.
    """
    artists = search_nearby_artists(
        db=db,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
        booking_mode=payload.booking_mode,
        limit=payload.limit,
        instant_only=payload.instant_only,
        location_type=payload.location_type,
        artist_type=payload.artist_type,
        service_type=payload.service_type,
        min_rating=payload.min_rating,
        price_min=payload.price_min,
        price_max=payload.price_max,
    )
    return GeoSearchResponse(
        artists=[GeoSearchArtistResult(**a) for a in artists],
        total=len(artists),
    )


# ═══════════════════════ Public Artist Profile ═══════════════════════

@router.get("/artist/{artist_id}/profile")
async def get_artist_profile(
    artist_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Public artist profile for customer-facing profile page.
    Returns: artist bio, stats, packages list, portfolio.
    No auth required.
    """
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    from app.Booking.models import ArtistPackage
    packages = db.query(ArtistPackage).filter(
        ArtistPackage.artist_id == artist_id,
        ArtistPackage.is_active == True,
        ArtistPackage.is_template == False
    ).order_by(ArtistPackage.created_at.asc()).all()

    return {
        "id": str(artist.id),
        "name": artist.name,
        "username": artist.username,
        "bio": artist.bio,
        "profile_pic_url": artist.profile_pic_url,
        "profession": artist.profession,
        "experience": artist.experience,
        "rating": float(artist.rating) if artist.rating else 0.0,
        "total_reviews": artist.total_reviews or 0,
        "total_bookings": artist.total_bookings or 0,
        "city": artist.city,
        "kyc_verified": artist.kyc_verified,
        "skills": artist.skills,
        "portfolio": artist.portfolio,
        "booking_mode": artist.booking_mode,
        "artist_type": artist.artist_type,
        "instant_toggle": artist.instant_toggle if hasattr(artist, "instant_toggle") else False,
        "packages": [
            {
                "id": str(p.id),
                "name": p.name,
                "price": float(p.price),
                "duration_minutes": p.duration_minutes,
                "category": p.category,
                "service_type": p.service_type,
                "description": p.description,
                "image_url": p.image_url,
                "module": p.module,
            }
            for p in packages
        ],
    }


@router.get("/artist/{artist_id}/reviews")
async def get_artist_reviews(
    artist_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    # Reviews are introduced in Sprint 5 (STEP_05). Until the Review model
    # and its migration land, this endpoint returns an empty page so
    # customer-facing screens can render a placeholder without error.
    return {"reviews": [], "total": 0, "page": page, "pages": 0}


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
    actor: tuple = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Get a booking by ID. Caller must be the customer or artist on the booking."""
    booking = get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    actor_obj, kind = actor
    if kind == "customer" and booking.customer_id != actor_obj.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if kind == "artist" and booking.artist_id != actor_obj.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    return _booking_to_response(booking, db)


@router.get("/{booking_id}/detail", response_model=BookingDetailResponse)
def get_booking_full_detail(
    booking_id: UUID,
    actor: tuple = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Full booking detail (artist mini + customer mini + packages). Caller must be on the booking."""
    booking = get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    actor_obj, kind = actor
    if kind == "customer" and booking.customer_id != actor_obj.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if kind == "artist" and booking.artist_id != actor_obj.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    artist = db.query(Artist).filter(Artist.id == booking.artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist on booking not found")

    return BookingDetailResponse(
        booking=_booking_to_response(booking, db),
        artist=ArtistMini(
            id=artist.id,
            name=artist.name,
            username=artist.username,
            profile_pic_url=artist.profile_pic_url,
            rating=float(artist.rating or 0),
            total_reviews=artist.total_reviews or 0,
            phone_number=artist.phone_number,
        ),
        customer=CustomerMini(
            name=booking.customer_name,
            phone=booking.customer_phone,
            address=booking.customer_address,
            latitude=booking.customer_lat,
            longitude=booking.customer_lng,
        ),
        cancelled_by=booking.cancelled_by,
        cancellation_reason=booking.cancellation_reason,
    )


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    payload: BookingCancelRequest = BookingCancelRequest(),
    actor: tuple = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    """Cancel a booking. Caller must be customer or artist on the booking. Allowed only in pending/accepted state."""
    booking = get_booking(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    actor_obj, kind = actor
    if kind == "customer" and booking.customer_id != actor_obj.id:
        raise HTTPException(status_code=403, detail="Not your booking")
    if kind == "artist" and booking.artist_id != actor_obj.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    if booking.status not in ("pending", "accepted"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a booking in '{booking.status}' state",
        )

    booking.status = "cancelled"
    booking.cancelled_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    booking.cancelled_by = kind
    booking.cancellation_reason = payload.reason
    db.commit()
    db.refresh(booking)

    # Best-effort: cancel the redis timer if any.
    try:
        await cancel_booking_timer(str(booking.id))
    except Exception as e:
        logger.warning(f"Failed to cancel redis timer for {booking.id}: {e}")

    # Notify the *other* party.
    payload_msg = {
        "type": "booking_cancelled",
        "booking_id": str(booking.id),
        "cancelled_by": kind,
        "reason": payload.reason,
    }
    if kind == "customer":
        await ws_manager.notify_artist(str(booking.artist_id), payload_msg)
    else:
        await ws_manager.notify_customer(str(booking.customer_id), payload_msg)

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


@router.get("/artist/active")
def get_artist_active_booking(
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Most recent non-terminal booking for the current artist (or null).
    Used by the FE incoming-popup to recover state after a refresh."""
    booking = get_active_booking_for_artist(db, current_artist.id)
    if not booking:
        return None
    return _booking_to_response(booking, db)


@router.get("/customer/active")
def get_customer_active_booking(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Most recent non-terminal booking for the current customer (or null).
    Used by the FE waiting page to recover state after a refresh."""
    booking = get_active_booking_for_customer(db, current_user.id)
    if not booking:
        return None
    return _booking_to_response(booking, db)


@router.get("/artist/list", response_model=BookingListResponse)
def list_artist_bookings(
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
    status: Optional[str] = Query(
        default=None,
        description=f"Filter by status. One of: {', '.join(ALLOWED_BOOKING_STATUSES)}",
    ),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """List bookings for the current artist, optionally filtered by status."""
    if status is not None and status not in ALLOWED_BOOKING_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Must be one of: {', '.join(ALLOWED_BOOKING_STATUSES)}",
        )
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


# ═══════════════════════ Sprint 1 — New Package Endpoints ═══════════════════════

@router.get("/packages/templates", response_model=List[ArtistPackageResponse])
async def get_package_templates(
    service_type: Optional[str] = Query(None),
    duration_minutes: Optional[int] = Query(None),
    module: str = Query("instant"),
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Get platform templates. Filtered by service_type and/or duration_minutes."""
    from app.Booking.models import ArtistPackage

    query = db.query(ArtistPackage).filter(
        ArtistPackage.is_template == True,
        ArtistPackage.is_active == True,
        ArtistPackage.module == module,
    )
    if service_type:
        query = query.filter(ArtistPackage.service_type == service_type)
    if duration_minutes:
        query = query.filter(ArtistPackage.duration_minutes == duration_minutes)
    return query.order_by(ArtistPackage.created_at.asc()).all()


@router.get("/artist/packages/my", response_model=List[ArtistPackageResponse])
async def get_my_packages(
    module: Optional[str] = Query(None),
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Get current artist's own packages."""
    from app.Booking.models import ArtistPackage

    query = db.query(ArtistPackage).filter(
        ArtistPackage.artist_id == current_artist.id,
        ArtistPackage.is_active == True,
        ArtistPackage.is_template == False,
    )
    if module:
        query = query.filter(ArtistPackage.module == module)
    return query.order_by(ArtistPackage.created_at.desc()).all()


@router.post(
    "/artist/packages/from-template/{template_id}",
    response_model=ArtistPackageResponse,
    status_code=201,
)
async def create_package_from_template(
    template_id: UUID,
    overrides: Optional[ArtistPackageUpdate] = None,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db),
):
    """Create a package from a platform template with optional overrides."""
    from app.Booking.models import ArtistPackage

    template = db.query(ArtistPackage).filter(
        ArtistPackage.id == template_id,
        ArtistPackage.is_template == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    override_data = overrides.model_dump(exclude_unset=True) if overrides else {}

    new_pkg = ArtistPackage(
        id=uuid_lib.uuid4(),
        artist_id=current_artist.id,
        name=override_data.get("name", template.name),
        description=override_data.get("description", template.description),
        price=override_data.get("price", float(template.price)),
        duration_minutes=override_data.get("duration_minutes", template.duration_minutes),
        category=override_data.get("category", template.category),
        service_type=override_data.get("service_type", template.service_type),
        image_url=override_data.get("image_url", template.image_url),
        module=template.module,
        is_template=False,
        is_active=True,
    )
    db.add(new_pkg)
    db.commit()
    db.refresh(new_pkg)
    return new_pkg


# ═══════════════════════ WebSocket Endpoints ═══════════════════════

def _verify_ws_token(token: Optional[str], expected_id: str, table_class, db: Session) -> bool:
    """Validate the ?token= query param matches the path id. Returns True on success.

    Caller must close the websocket on False (use code=4401).
    """
    if not token:
        return False
    try:
        decoded = verify_firebase_token(token)
    except Exception:
        return False
    firebase_uid = decoded.get("uid")
    if not firebase_uid:
        return False
    row = db.query(table_class).filter(table_class.firebase_uid == firebase_uid).first()
    return bool(row and str(row.id) == expected_id)


@router.websocket("/ws/artist/{artist_id}")
async def websocket_artist(
    websocket: WebSocket,
    artist_id: str,
    token: Optional[str] = Query(default=None),
):
    """Artist real-time stream. Auth: ?token=<firebase_id_token> matching the artist."""
    # Verify in a short-lived session (we can't use Depends easily on websockets here).
    from app.Booking.database import SessionLocal
    db = SessionLocal()
    try:
        if not _verify_ws_token(token, artist_id, Artist, db):
            await websocket.close(code=4401)  # Unauthorized
            return
    finally:
        db.close()

    await ws_manager.connect_artist(artist_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_artist(artist_id)
        logger.info(f"Artist {artist_id} WebSocket disconnected")


@router.websocket("/ws/customer/{customer_id}")
async def websocket_customer(
    websocket: WebSocket,
    customer_id: str,
    token: Optional[str] = Query(default=None),
):
    """Customer real-time stream. Auth: ?token=<firebase_id_token> matching the customer."""
    from app.Booking.database import SessionLocal
    db = SessionLocal()
    try:
        if not _verify_ws_token(token, customer_id, User, db):
            await websocket.close(code=4401)
            return
    finally:
        db.close()

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
