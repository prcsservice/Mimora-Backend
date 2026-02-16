# app/auth/schemas.py
from typing import List, Optional, Tuple, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class OTPRequest(BaseModel):
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None



class OAuthRequest(BaseModel):
    latitude: float | None = None
    longitude: float | None = None


class ArtistOAuthRequest(BaseModel):
    phone_number: str | None = None
    birthdate: datetime | None = None
    gender: str | None = None
    experience: str | None = None
    bio: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    mode: str = "login"  # "login" or "signup"


class UserLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    flat_building: str | None = None  # Optional
    street_area: str
    landmark: str | None = None  # Optional
    pincode: str
    city: str
    state: str



class EmailSignupRequest(BaseModel):
    username: str
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str





class CheckUserRequest(BaseModel):
    identifier: str  # email or phone number
    type: str  # "email" or "phone"


class CheckUserResponse(BaseModel):
    exists: bool
    user_type: str | None = None


class EmailLoginRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: UUID
    firebase_uid: str
    email: EmailStr | None = None    # Optional for phone-only users
    phone_number: str | None = None  # Phone number
    name: str | None
    provider: str
    token: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    flat_building: str | None = None
    street_area: str | None = None
    landmark: str | None = None
    address: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True    # for SQLAlchemy



#  ---------------------------------------------------------ARTIST------------------------------------------------------------------------------

class ArtistCreate(BaseModel):
    username: str
    bio: str
    email: EmailStr
    phone_number: str
    profession: List[str]
    experience: str
    city: str
    address: str
    travel_radius: float = Field(..., alias="travel_radius")
    latitude: float
    longitude: float
    location: Tuple[float, float]
    kyc_verified: bool
    bank_verified: bool
    portfolio: List[str]
    rating: float
    total_reviews: int

    class Config:
        populate_by_name = True 

class EmailArtistOTPRequest(BaseModel):
    email: EmailStr
    username: str


class ArtistVerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    phone_number: str | None = None
    birthdate: datetime | None = None
    gender: str | None = None
    experience: str | None = None
    bio: str | None = None

class ArtistUpdate(BaseModel):
    bio: Optional[str] = None
    profession: Optional[List[str]] = None
    city: Optional[str] = None


class ArtistProfileCompleteRequest(BaseModel):
    """Schema for completing artist profile after initial auth"""
    # Step 1: Personal Details
    phone_number: str | None = None
    birthdate: str | None = None  # DD/MM/YYYY format from frontend
    gender: str | None = None
    experience: str | None = None
    bio: str | None = None
    profile_pic_url: str | None = None
    name: str | None = None
    username: str | None = None

    # Step 3: Professional Info
    how_did_you_learn: str | None = None  # 'professional', 'self-learned', 'apprentice'
    certificate_url: str | None = None
    profession: List[str] | None = None

    # Step 4: Address
    flat_building: str | None = None
    street_area: str | None = None
    landmark: str | None = None
    pincode: str | None = None
    city: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    # Step 2: Booking Preferences
    booking_mode: str | None = None  # 'instant' | 'flexi' | 'both'
    skills: List[str] | None = None
    event_types: List[str] | None = None
    service_location: str | None = None  # 'client' | 'studio' | 'both'
    travel_willingness: List[str] | None = None
    studio_address: str | None = None  # JSON string
    working_hours: str | None = None  # JSON string

    # Step 3: Portfolio
    portfolio: List[str] | None = None

    # Step 4: Bank Details
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    bank_ifsc: str | None = None
    upi_id: str | None = None

    # Step completion control
    mark_complete: bool = False  # Only mark profile_completed=True when all steps done


class ArtistResponse(BaseModel):
    id: UUID
    firebase_uid: str | None = None
    name: str | None = None
    username: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    birthdate: datetime | None = None
    gender: str | None = None
    bio: str | None = None
    experience: str | None = None
    provider: str | None = None
    profession: List[str] | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    total_reviews: int | None = None
    kyc_verified: bool | None = None
    created_at: datetime | None = None
    token: str | None = None

    # Profile completion tracking
    profile_completed: bool = False
    profile_pic_url: str | None = None
    how_did_you_learn: str | None = None
    certificate_url: str | None = None
    flat_building: str | None = None
    street_area: str | None = None
    landmark: str | None = None
    pincode: str | None = None
    state: str | None = None

    # Booking Preferences
    booking_mode: str | None = None
    skills: list | None = None
    event_types: list | None = None
    service_location: str | None = None
    travel_willingness: list | None = None
    studio_address: str | None = None
    working_hours: str | None = None

    # Portfolio
    portfolio: list | None = None

    # Bank Details
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    bank_ifsc: str | None = None
    upi_id: str | None = None
    bank_verified: bool | None = None

    class Config:
        from_attributes = True