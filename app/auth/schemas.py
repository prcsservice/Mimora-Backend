# app/auth/schemas.py
from typing import List, Optional
from uuid import UUID
from proto import Field
from pydantic import BaseModel, EmailStr,Field
from datetime import datetime
from geoalchemy2 import Geography
from typing import Tuple


class OTPRequest(BaseModel):
    name: str | None = None


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


class UserResponse(BaseModel):
    id: UUID
    firebase_uid: str            # ✅ ADD THIS
    email: EmailStr
    name: str | None
    provider: str
    token: str | None = None  # ✅ Optional token for auth flows
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

class ArtistUpdate(BaseModel):
    bio: Optional[str] = None
    profession: Optional[List[str]] = None
    city: Optional[str] = None

class ArtistResponse(BaseModel):
    id: UUID
    username: str
    bio: str
    profession: List[str]
    city: str
    rating: float
    total_reviews: int
    kyc_verified: bool
    
    class Config:
        from_attributes = True