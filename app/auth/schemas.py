# app/auth/schemas.py
from typing import List, Optional, Tuple
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

    class Config:
        from_attributes = True