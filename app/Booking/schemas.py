"""
Booking Microservice — Pydantic Schemas
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


# ═══════════════════════ Geo-Search ═══════════════════════

class GeoSearchRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = Field(default=20.0, ge=1, le=100, description="Search radius in km")
    booking_mode: Optional[str] = None  # Filter: "instant" | "flexi" | "both"
    limit: int = Field(default=20, ge=1, le=50)


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
    duration_minutes: Optional[int] = Field(None, gt=0)
    category: Optional[str] = None


class ArtistPackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    duration_minutes: Optional[int] = Field(None, gt=0)
    category: Optional[str] = None
    is_active: Optional[bool] = None


class ArtistPackageResponse(BaseModel):
    id: UUID
    artist_id: UUID
    name: str
    description: Optional[str] = None
    price: float
    duration_minutes: Optional[int] = None
    category: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


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
