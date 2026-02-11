import datetime

import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Integer,
    ForeignKey,
    ARRAY,
    DateTime,
    Text,
   
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.auth.database import Base


class User(Base):
    __tablename__ = "customer"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String, unique=True, index=True, nullable=True)

    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True)

    city = Column(String, nullable=True)
    address = Column(String, nullable=True)
    flat_building = Column(String, nullable=True)
    street_area = Column(String, nullable=True)
    landmark = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    state = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    travel_radius = Column(Integer, default=10)  # in kilometers
    location = Column(Geography(geometry_type="POINT", srid=4326))

    provider = Column(String)  # google | phone | email
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class EmailOTP(Base):
    __tablename__ = "email_otps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False)
    username = Column(String, nullable=False)  # store username here
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)


#  ---------------------------------------------------------ARTIST------------------------------------------------------------------------------

class Artist(Base):
    """Artist/Makeup Artist Model"""
    __tablename__ = "artists"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Profile Information
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True)
    birthdate = Column(DateTime, nullable=True)
    gender = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    
    # Professional Details
    profession = Column(ARRAY(String), default=list)  # ["Bridal Makeup", "Party Makeup"]
    experience = Column(String, nullable=True)  # "beginner" | "intermediate" | "expert"

    # Location Details
    city = Column(String, nullable=False)
    address = Column(String, nullable=False)
    flat_building = Column(String, nullable=True)
    street_area = Column(String, nullable=True)
    landmark = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    state = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    travel_radius = Column(Integer, default=10)  # in kilometers
    location = Column(Geography(geometry_type="POINT", srid=4326))

    # KYC Verification Status
    kyc_verified = Column(Boolean, default=False, index=True)
    bank_verified = Column(Boolean, default=False, index=True)
    kyc_id = Column(String, nullable=True)  # Meon's KYC ID

    # Portfolio
    portfolio = Column(ARRAY(String), default=list)  # Array of image URLs

    # Stats and Ratings
    rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    total_bookings = Column(Integer, default=0)

    # Account Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Artist(id={self.id}, username={self.username}, kyc_verified={self.kyc_verified})>"

    @property
    def is_fully_verified(self):
        """Check if artist has completed all verifications"""
        return self.kyc_verified and self.bank_verified


class KYCRequest(Base):
    """KYC Verification Request Tracking"""
    __tablename__ = "kyc_requests"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Key to Artist
    artist_id = Column(UUID(as_uuid=True), ForeignKey("artists.id"), nullable=False, index=True)

    # KYC Provider Details
    provider = Column(String, default="meon", nullable=False)  # "meon"
    provider_kyc_id = Column(String, nullable=True, index=True)  # Meon's KYC ID
    
    # Two-step Verification Tracking
    document_verified = Column(Boolean, default=False)  # Aadhar/PAN verification
    face_verified = Column(Boolean, default=False)  # Face/Liveness verification
    current_step = Column(String, default="document", nullable=False)  # "document" | "face" | "complete"
    
    # Status Tracking
    status = Column(String, default="pending", nullable=False)  
    # Possible values: "pending", "in_progress", "document_verified", "verified", "failed", "cancelled"
    
    # Store full verification response from Meon
    verification_data = Column(Text, nullable=True)  # JSON string

    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<KYCRequest(id={self.id}, artist_id={self.artist_id}, status={self.status})>"