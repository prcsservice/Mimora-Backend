"""
Booking Microservice — Pydantic Schemas
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


ALLOWED_SERVICE_TYPES = ["makeup", "nail", "hairstyle", "mehendi", "saree_draping", "saree_pleating"]
ALLOWED_MODULES = ["instant", "flexi", "workshop"]


# ═══════════════════════ Geo-Search ═══════════════════════

class GeoSearchRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = Field(default=20.0, ge=1, le=100, description="Search radius in km")
    booking_mode: Optional[str] = None  # Filter: "instant" | "flexi" | "both"
    limit: int = Field(default=20, ge=1, le=50)

    # Sprint 2 — Discovery filters
    location_type: Optional[str] = None   # "client" or "studio"
    artist_type: Optional[str] = None     # "client_only", "studio_only", "both"
    service_type: Optional[str] = None    # "makeup", "nail", "hairstyle" etc.
    instant_only: bool = True             # default True — only show instant artists
    min_rating: Optional[float] = None    # e.g. 4.0
    price_min: Optional[float] = None
    price_max: Optional[float] = None


class GeoSearchArtistResult(BaseModel):
    id: UUID
    name: Optional[str] = None
    username: Optional[str] = None
    profile_pic_url: Optional[str] = None
    profession: Optional[list] = None
    experience: Optional[str] = None
    rating: float = 0.0
    total_reviews: int = 0
    total_bookings: int = 0
    distance_km: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    booking_mode: Optional[str] = None
    skills: Optional[list] = None

    # Sprint 2 — new fields for search results cards
    artist_type: Optional[str] = None
    instant_toggle: bool = False
    city: Optional[str] = None
    packages_preview: list = []   # first 3 packages for the card thumbnails

    class Config:
        from_attributes = True


class GeoSearchResponse(BaseModel):
    artists: List[GeoSearchArtistResult]
    total: int


# ═══════════════════════ Artist Packages ═══════════════════════

class ArtistPackageCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    duration_minutes: Optional[int] = Field(None, ge=20, le=90)
    category: Optional[str] = None
    service_type: Optional[str] = None
    image_url: Optional[str] = None
    module: str = "instant"

    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_SERVICE_TYPES:
            raise ValueError(f'service_type must be one of: {ALLOWED_SERVICE_TYPES}')
        return v

    @field_validator('module')
    @classmethod
    def validate_module(cls, v):
        if v not in ALLOWED_MODULES:
            raise ValueError(f'module must be one of: {ALLOWED_MODULES}')
        return v


class ArtistPackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    duration_minutes: Optional[int] = Field(None, ge=20, le=90)
    category: Optional[str] = None
    service_type: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_SERVICE_TYPES:
            raise ValueError(f'service_type must be one of: {ALLOWED_SERVICE_TYPES}')
        return v


class ArtistPackageResponse(BaseModel):
    id: UUID
    artist_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    price: float
    duration_minutes: Optional[int] = None
    category: Optional[str] = None
    service_type: Optional[str] = None
    image_url: Optional[str] = None
    module: str = "instant"
    is_active: bool
    is_template: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateFilterParams(BaseModel):
    service_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    module: str = "instant"


# ═══════════════════════ Instant Booking ═══════════════════════

class InstantBookingRequest(BaseModel):
    artist_id: UUID
    package_ids: List[UUID] = Field(..., min_length=1, description="At least one package required")
    latitude: float
    longitude: float
    address: Optional[str] = None
    customer_notes: Optional[str] = None
    fallback_artist_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Ordered list of backup artists if primary declines/expires"
    )


class BookingAcceptDecline(BaseModel):
    action: str = Field(..., pattern="^(accept|decline)$")


class BookingPackageDetail(BaseModel):
    package_id: UUID
    name: str
    price: float

    class Config:
        from_attributes = True


class BookingResponse(BaseModel):
    id: UUID
    customer_id: UUID
    artist_id: UUID
    booking_type: str
    status: str
    total_amount: float
    travel_charge: float
    grand_total: float
    customer_lat: Optional[float] = None
    customer_lng: Optional[float] = None
    customer_address: Optional[str] = None
    artist_lat: Optional[float] = None
    artist_lng: Optional[float] = None
    distance_km: Optional[float] = None
    expires_at: Optional[datetime] = None
    customer_notes: Optional[str] = None
    packages: List[BookingPackageDetail] = []
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    bookings: List[BookingResponse]
    total: int


# ═══════════════════════ Sprint 3 — Cancel + Detail ═══════════════════════

ALLOWED_BOOKING_STATUSES = ("pending", "accepted", "declined", "expired", "cancelled", "completed")


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class ArtistMini(BaseModel):
    id: UUID
    name: Optional[str] = None
    username: Optional[str] = None
    profile_pic_url: Optional[str] = None
    rating: float = 0.0
    total_reviews: int = 0
    phone_number: Optional[str] = None


class CustomerMini(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BookingDetailResponse(BaseModel):
    booking: BookingResponse
    artist: ArtistMini
    customer: CustomerMini
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
