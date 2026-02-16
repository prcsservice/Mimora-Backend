"""
Complete Backend KYC Implementation - Routes
app/auth/routes.py
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
import uuid
import httpx
import os
import hmac
import hashlib
import json

logger = logging.getLogger(__name__)
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.auth.database import get_db
from app.auth.models import Artist, KYCRequest, EmailArtistOTP, User
from app.auth.schemas import (
    ArtistCreate, ArtistResponse, UserLocationUpdate,
    ArtistOAuthRequest, EmailSignupRequest, EmailLoginRequest,
    CheckUserRequest, ArtistVerifyOTPRequest, OTPRequest,
    ArtistProfileCompleteRequest,EmailArtistOTPRequest
)
from app.auth.firebase import verify_firebase_token
from app.auth.utils.otp import generate_otp, hash_otp, verify_otp, otp_expiry
from app.auth.utils.send_email import send_otp_email
from dotenv import load_dotenv
from app.auth.utils.current_user import get_current_artist
import firebase_admin
from firebase_admin import auth as firebase_auth
# Load environment variables from .env file
load_dotenv()
limiter = Limiter(key_func=get_remote_address)

# # Debug: Print loaded variables
# print(f"DEBUG - MEON_API_BASE_URL: {os.getenv('MEON_API_BASE_URL')}")
# print(f"DEBUG - MEON_API_KEY: {os.getenv('MEON_API_KEY')}")

router = APIRouter()




@router.get("/auth/artist/me", response_model=ArtistResponse)
async def get_artist_profile(artist: Artist = Depends(get_current_artist)):
    """
    Get the authenticated artist's full profile.
    
    Used by frontend as fallback when localStorage is missing/corrupted.
    Returns all profile data including booking preferences, portfolio, and bank details.
    
    Requires: Firebase authentication token in Authorization header
    """
    return artist


@router.put("/auth/artist/location")
async def update_artist_location(
    payload: UserLocationUpdate,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db)
):
    """
    Update authenticated artist's location and address
    """
    current_artist.latitude = payload.latitude
    current_artist.longitude = payload.longitude
    current_artist.flat_building = payload.flat_building
    current_artist.street_area = payload.street_area
    current_artist.landmark = payload.landmark
    current_artist.pincode = payload.pincode
    current_artist.city = payload.city
    current_artist.state = payload.state

    # Build full address string
    address_parts = [p for p in [payload.flat_building, payload.street_area, payload.landmark, payload.city, payload.state, payload.pincode] if p]
    current_artist.address = ", ".join(address_parts)

    # Update PostGIS geometry column
    current_artist.location = f"POINT({payload.longitude} {payload.latitude})"

    db.commit()
    db.refresh(current_artist)

    return current_artist


@router.post("/auth/artist/register", response_model=ArtistResponse)
async def become_artist(
    data: ArtistCreate, 
    db: Session = Depends(get_db)
):
    """
    Register new artist profile
    KYC verification will be done separately
    """
    # Check username availability
    existing = db.query(Artist).filter(Artist.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already taken")
    
    # Create artist profile - KYC starts as False
    artist = Artist(
        username=data.username,
        email=data.email,
        phone_number=data.phone_number,
        bio=data.bio,
        profession=data.profession,
        experience=data.experience,
        city=data.city,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude,
        travel_radius=data.travel_radius or 10,
        location=data.location,
        portfolio=data.portfolio or [],
        
        # Verification status - always start as False
        kyc_verified=False,
        bank_verified=False,
        
        # Stats
        rating=0.0,
        total_reviews=0,
    )
    
    db.add(artist)
    db.commit()
    db.refresh(artist)
    
    return artist


@router.post("/auth/artist/check")
@limiter.limit("10/minute")  # Rate limit: 10 checks per minute
async def check_artist_exists(
    request: Request,
    payload: CheckUserRequest,
    db: Session = Depends(get_db)
):
    """
    Check if an artist exists by email or phone.
    Also cross-checks the customer table for the crossover scenario.
    """
    try:
        from app.auth.schemas import CheckUserResponse
        
        print(f"DEBUG check_artist_exists: type={payload.type}, identifier={payload.identifier}")
        
        # Check Artist table first
        if payload.type == "email":
            artist = db.query(Artist).filter(Artist.email == payload.identifier).first()
        elif payload.type == "phone":
            artist = db.query(Artist).filter(Artist.phone_number == payload.identifier).first()
        else:
            raise HTTPException(status_code=400, detail="Invalid type. Use 'email' or 'phone'")
        
        if artist:
            print(f"DEBUG: Found artist: {artist.id}")
            return CheckUserResponse(exists=True, user_type="artist")
        
        # Not an artist — check if they're a customer
        if payload.type == "email":
            customer = db.query(User).filter(User.email == payload.identifier).first()
        else:
            customer = db.query(User).filter(User.phone_number == payload.identifier).first()
        
        if customer:
            print(f"DEBUG: Found customer: {customer.id}")
            return CheckUserResponse(exists=True, user_type="customer")
        
        print("DEBUG: User not found in either table")
        return CheckUserResponse(exists=False, user_type=None)
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in check_artist_exists: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/auth/artist/oauth", response_model=ArtistResponse)
@limiter.limit("20/minute")  # Rate limit for OAuth login
async def oauth_login(
    request: Request,
    payload: ArtistOAuthRequest = ArtistOAuthRequest(),
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
  
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = authorization.split(" ")[1]
    
    # Verify token with Firebase
    try:
        decoded = verify_firebase_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=401, 
            detail=f"Token verification failed: {str(e)}"
        )
    
    # Extract data from decoded token
    email = decoded.get("email")
    name = decoded.get("name")
    firebase_uid = decoded.get("uid")
    provider = decoded.get("firebase", {}).get("sign_in_provider", "unknown")
    
    # Validate required fields
    if not email:
        raise HTTPException(
            status_code=400, 
            detail="Email not found in token. OAuth provider must provide email."
        )
    
    if not firebase_uid:
        raise HTTPException(
            status_code=400, 
            detail="Firebase UID not found in token"
        )
    
    # Check if user exists by email
    user = db.query(Artist).filter(Artist.email == email).first()
    
    if user:
        # Existing user - update if needed
        updated = False
        
        if user.firebase_uid != firebase_uid:
            user.firebase_uid = firebase_uid
            updated = True
        
        if user.provider != provider:
            user.provider = provider
            updated = True
        
        # Update location if provided
        if payload.latitude and payload.longitude:
            user.latitude = payload.latitude
            user.longitude = payload.longitude
            updated = True
        
        if updated:
            db.commit()
            db.refresh(user)
    else:
        # NEW: Check if email exists as Customer (prevent cross-account duplicates)
        existing_customer = db.query(User).filter(User.email == email).first()
        if existing_customer:
            raise HTTPException(
                status_code=400,
                detail="This email is registered as a customer account. Please use the customer login."
            )
        
        # New user
        if payload.mode == "signup":
            # Generate username from email (part before @)
            base_username = email.split("@")[0].lower().replace(".", "_")
            username = base_username
            # Ensure uniqueness
            counter = 1
            while db.query(Artist).filter(Artist.username == username).first():
                username = f"{base_username}{counter}"
                counter += 1

            # Create minimal profile for signup flow
            user = Artist(
                firebase_uid=firebase_uid,
                email=email,
                name=name,
                username=username,
                provider=provider,
                latitude=payload.latitude,
                longitude=payload.longitude,
                profile_completed=False,
                kyc_verified=False,
                rating=0.0,
                total_reviews=0
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Login mode - don't auto-create new artists
            raise HTTPException(
                status_code=404,
                detail="No artist account found. Please sign up first."
            )
    
    return user


# ============ Phone OTP Auth (NEW) ============
@router.post("/auth/artist/otp", response_model=ArtistResponse)
@limiter.limit("20/minute")
async def otp_auth(
    request: Request,
    payload: OTPRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Authenticate artist with Firebase phone OTP.
    Creates minimal artist profile if new user.
    """
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = authorization.split(" ")[1]
    
    # Verify Firebase token
    try:
        decoded = verify_firebase_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token verification failed: {str(e)}"
        )
    
    # Extract phone number and firebase_uid
    phone_number = decoded.get("phone_number")
    firebase_uid = decoded.get("uid")
    provider = "phone"
    
    if not firebase_uid:
        raise HTTPException(status_code=400, detail="Firebase UID not found in token")
    
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number not found in token")
    
    # Check if artist exists by phone number or firebase_uid
    artist = db.query(Artist).filter(Artist.phone_number == phone_number).first()
    if not artist:
        artist = db.query(Artist).filter(Artist.firebase_uid == firebase_uid).first()
    
    if artist:
        # Existing artist - update firebase_uid and provider if needed
        updated = False
        
        if artist.firebase_uid != firebase_uid:
            artist.firebase_uid = firebase_uid
            updated = True
        
        if artist.provider != provider:
            artist.provider = provider
            updated = True
        
        # Update name if provided and not already set
        if payload.name and not artist.name:
            artist.name = payload.name
            updated = True
        
        # Update location if provided
        if payload.latitude and payload.longitude:
            artist.latitude = payload.latitude
            artist.longitude = payload.longitude
            updated = True
        
        if updated:
            db.commit()
            db.refresh(artist)
        
        print(f"Artist {artist.id} logged in via phone OTP")
    else:
        # Create new artist with minimal data
        artist = Artist(
            firebase_uid=firebase_uid,
            phone_number=phone_number,
            name=payload.name,
            provider=provider,
            latitude=payload.latitude,
            longitude=payload.longitude,
            profile_completed=False,
            kyc_verified=False,
            rating=0.0,
            total_reviews=0
        )
        db.add(artist)
        db.commit()
        db.refresh(artist)
        print(f"Created new artist {artist.id} via phone OTP")
    
    return artist


# ============ Profile Completion (NEW) ============
@router.put("/auth/artist/profile", response_model=ArtistResponse)
async def complete_artist_profile(
    payload: ArtistProfileCompleteRequest,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db)
):
    """
    Complete artist profile with additional details.
    Called after initial authentication to fill in all profile fields.
    """
    # Convert birthdate from DD/MM/YYYY to datetime
    if payload.birthdate:
        try:
            day, month, year = payload.birthdate.split('/')
            current_artist.birthdate = datetime(int(year), int(month), int(day))
        except (ValueError, AttributeError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid birthdate format. Use DD/MM/YYYY: {str(e)}"
            )
    
    # Update personal details
    if payload.name is not None:
        current_artist.name = payload.name
    if payload.username is not None:
        # Check username uniqueness
        existing = db.query(Artist).filter(
            Artist.username == payload.username,
            Artist.id != current_artist.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        current_artist.username = payload.username
    if payload.phone_number is not None:
        # Check phone uniqueness
        existing = db.query(Artist).filter(
            Artist.phone_number == payload.phone_number,
            Artist.id != current_artist.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Phone number already registered")
        current_artist.phone_number = payload.phone_number
    if payload.gender is not None:
        current_artist.gender = payload.gender
    if payload.experience is not None:
        current_artist.experience = payload.experience
    if payload.bio is not None:
        current_artist.bio = payload.bio
    if payload.profile_pic_url is not None:
        current_artist.profile_pic_url = payload.profile_pic_url
    
    # Update professional info
    if payload.how_did_you_learn is not None:
        current_artist.how_did_you_learn = payload.how_did_you_learn
    if payload.certificate_url is not None:
        current_artist.certificate_url = payload.certificate_url
    if payload.profession is not None:
        current_artist.profession = payload.profession
    
    # Update booking preferences
    if payload.booking_mode is not None:
        current_artist.booking_mode = payload.booking_mode
    if payload.skills is not None:
        current_artist.skills = payload.skills
    if payload.event_types is not None:
        current_artist.event_types = payload.event_types
    if payload.service_location is not None:
        current_artist.service_location = payload.service_location
    if payload.travel_willingness is not None:
        current_artist.travel_willingness = payload.travel_willingness
    if payload.studio_address is not None:
        current_artist.studio_address = payload.studio_address
    if payload.working_hours is not None:
        current_artist.working_hours = payload.working_hours

    # Update portfolio (Step 3)
    if payload.portfolio is not None:
        current_artist.portfolio = payload.portfolio

    # Update bank details (Step 4)
    if payload.bank_account_name is not None:
        current_artist.bank_account_name = payload.bank_account_name
    if payload.bank_account_number is not None:
        current_artist.bank_account_number = payload.bank_account_number
    if payload.bank_name is not None:
        current_artist.bank_name = payload.bank_name
    if payload.bank_ifsc is not None:
        current_artist.bank_ifsc = payload.bank_ifsc
    if payload.upi_id is not None:
        current_artist.upi_id = payload.upi_id

    # Update address
    if payload.flat_building is not None:
        current_artist.flat_building = payload.flat_building
    if payload.street_area is not None:
        current_artist.street_area = payload.street_area
    if payload.landmark is not None:
        current_artist.landmark = payload.landmark
    if payload.pincode is not None:
        current_artist.pincode = payload.pincode
    if payload.city is not None:
        current_artist.city = payload.city
    if payload.state is not None:
        current_artist.state = payload.state
    if payload.latitude is not None and payload.longitude is not None:
        current_artist.latitude = payload.latitude
        current_artist.longitude = payload.longitude
    
    # Build address string from components
    addr_parts = [p for p in [
        current_artist.flat_building,
        current_artist.street_area,
        current_artist.landmark,
        current_artist.city,
        current_artist.state,
        current_artist.pincode
    ] if p]
    if addr_parts:
        current_artist.address = ", ".join(addr_parts)
    
    # Only mark profile as completed when all steps are done
    if payload.mark_complete:
        current_artist.profile_completed = True
    
    db.commit()
    db.refresh(current_artist)
    print(f"Artist {current_artist.id} completed profile")
    
    return current_artist


@router.post("/auth/artist/email")
@limiter.limit("5/minute")  # Strict limit to prevent OTP spam
async def email_signup(
    request: Request,
    payload: EmailArtistOTPRequest,
    db: Session = Depends(get_db)
):

    # Delete expired OTPs for this email
    expired_otps = db.query(EmailArtistOTP).filter(
        EmailArtistOTP.email == payload.email,
        EmailArtistOTP.expires_at < datetime.utcnow()
    ).all()
    
    if expired_otps:
        for expired_otp in expired_otps:
            db.delete(expired_otp)
        db.commit()
        print(f"Deleted {len(expired_otps)} expired OTP(s) for {payload.email}")
    # 1️⃣ Generate OTP
    otp = generate_otp()

    # 2️⃣ Store OTP + username
    otp_entry = EmailArtistOTP(
        email=payload.email,
        username=payload.username,
        otp_hash=hash_otp(otp),
        expires_at=otp_expiry()
    )

    db.add(otp_entry)
    db.commit()

    # 3️⃣ Send OTP email
    send_otp_email(payload.email, otp)

    return {"message": "OTP sent to your email", "email": payload.email}


@router.post("/auth/artist/email/verify", response_model=ArtistResponse)
@limiter.limit("10/minute")  # Prevent brute-force OTP guessing
async def verify_email_otp(
    request: Request,
    payload: ArtistVerifyOTPRequest,
    db: Session = Depends(get_db)
):
    # 1️⃣ Get the latest OTP record for this email
    otp_record = (
        db.query(EmailArtistOTP)
        .filter(EmailArtistOTP.email == payload.email)
        .order_by(EmailArtistOTP.id.desc())
        .first()
    )

    if not otp_record:
        print(f"DEBUG: OTP not found for email {payload.email}")
        raise HTTPException(status_code=400, detail="OTP not found")

    # 2️⃣ Check expiry
    if otp_record.expires_at < datetime.utcnow():
        print(f"DEBUG: OTP expired for {payload.email}. Expires: {otp_record.expires_at}, Now: {datetime.utcnow()}")
        raise HTTPException(status_code=400, detail="OTP expired")

    # 3️⃣ Verify OTP
    if not verify_otp(payload.otp, otp_record.otp_hash):
        print(f"DEBUG: Invalid OTP for {payload.email}. Provided: {payload.otp}")
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # 4️⃣ Get the username from OTP record
    username = otp_record.username

    # 5️⃣ Delete the used OTP
    db.delete(otp_record)
    db.commit()

    # 6️⃣ Check if user already exists
    user = db.query(Artist).filter(Artist.email == payload.email).first()

    if not user:
        # 7️⃣ Create user in Firebase
        try:
            firebase_user = firebase_auth.create_user(
                email=payload.email,
                display_name=username
            )
        except firebase_auth.EmailAlreadyExistsError:
            firebase_user = firebase_auth.get_user_by_email(payload.email)

        # 8️⃣ Create artist in DB
        user = Artist(
            email=payload.email,
            username=username,
            name=username,
            phone_number=payload.phone_number,
            birthdate=payload.birthdate,
            gender=payload.gender,
            experience=payload.experience,
            bio=payload.bio,
            provider="email",
            firebase_uid=firebase_user.uid,
            profile_completed=False,
            kyc_verified=False,
            rating=0.0,
            total_reviews=0
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 9️⃣ Generate Firebase Custom Token
    try:
        custom_token = firebase_auth.create_custom_token(user.firebase_uid)
        if isinstance(custom_token, bytes):
            custom_token = custom_token.decode("utf-8")
        user.token = custom_token
    except Exception as e:
        print(f"Error generating custom token: {e}")

    return user


@router.post("/auth/artist/email/login")
@limiter.limit("5/minute")
async def email_login(
    request: Request,
    payload: EmailLoginRequest,
    db: Session = Depends(get_db)
):
    """
    LOGIN: Send OTP to email (email only, no username needed)
    
    Request: {"email": "user@example.com"}
    Response: {"message": "OTP sent to your email", "email": "user@example.com"}
    """
    # Check if artist exists
    user = db.query(Artist).filter(Artist.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered. Please signup first.")

    # Delete expired OTPs for this email
    expired_otps = db.query(EmailArtistOTP).filter(
        EmailArtistOTP.email == payload.email,
        EmailArtistOTP.expires_at < datetime.utcnow()
    ).all()
    
    if expired_otps:
        for expired_otp in expired_otps:
            db.delete(expired_otp)
        db.commit()
        print(f"Deleted {len(expired_otps)} expired OTP(s) for {payload.email}")

    # Generate OTP
    otp = generate_otp()
    
    # Store OTP with existing username
    otp_entry = EmailArtistOTP(
        email=payload.email,
        username=user.username or user.name,
        otp_hash=hash_otp(otp),
        expires_at=otp_expiry()
    )
    db.add(otp_entry)
    db.commit()
    
    # Send OTP email
    send_otp_email(payload.email, otp)
    
    return {"message": "OTP sent to your email", "email": payload.email}

@router.post("/kyc/start/{artist_id}")
async def start_kyc(
    artist_id: str,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db)
):
    """
    Initiate KYC process with Meon
    Returns hosted KYC URL for user to complete verification
    """
    # Validate and find artist
    try:
        artist_uuid = uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artist ID format")
    
    artist = db.query(Artist).filter(Artist.id == artist_uuid).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Check if already verified
    if artist.kyc_verified:
        return {
            "status": "already_verified",
            "message": "KYC already verified",
            "kyc_verified": True
        }
    
    # Check for existing in-progress KYC
    existing_kyc = db.query(KYCRequest).filter(
        KYCRequest.artist_id == artist.id,
        KYCRequest.status.in_(["pending", "in_progress"])
    ).first()
    
    if existing_kyc and existing_kyc.provider_kyc_id:
        return {
            "status": "in_progress",
            "message": "KYC already in progress",
            "kyc_id": existing_kyc.provider_kyc_id,
            "kyc_url": f"https://live.meon.co.in/verify/{existing_kyc.provider_kyc_id}"
        }
    
    # Create new KYC request
    kyc_request = KYCRequest(
        artist_id=artist.id,
        provider="meon",
        status="pending"
    )
    
    db.add(kyc_request)
    db.commit()
    db.refresh(kyc_request)
    
    # Call Meon API to initiate Aadhar/PAN verification
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Meon SSO KYC Route API for Aadhar/PAN verification
            base_url = os.getenv('MEON_API_BASE_URL', 'https://live.meon.co.in')
            redirect_url = os.getenv('MEON_REDIRECT_URL', 'https://www.google.com')
            
            # Build request body per Meon documentation for analyst workflow
            request_body = {
                "company": os.getenv('MEON_COMPANY_NAME', 'mimora'),
                "workflowName": os.getenv('MEON_KYC_WORKFLOW_NAME', 'analyst'),
                "secret_key": os.getenv('MEON_SECRET_KEY'),
                "notification": True,               
                "unique_keys": {
                    "artist_id": str(artist.id),
                    "reference_id": str(kyc_request.id)
                },
                "is_redirect": True,
                "redirect_url": redirect_url,
            }
            
            meon_url = f"{base_url}/get_sso_kyc_route"
            logger.info(f"Calling Meon SSO KYC API: {meon_url}")
            
            response = await client.post(
                meon_url,
                headers={"Content-Type": "application/json"},
                json=request_body
            )
            
            logger.info(f"Meon response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                try:
                    if not response.text:
                        raise HTTPException(
                            status_code=500,
                            detail="Empty response from Meon API"
                        )
                    
                    meon_data = response.json()
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid response from Meon API: {response.text[:100]}"
                    )
                
                # Check for API-level errors
                if meon_data.get("success") == False or meon_data.get("status") == False:
                    error_msg = meon_data.get("msg") or meon_data.get("message") or "Unknown error from Meon API"
                    logger.error(f"Meon API error: {error_msg}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Meon API error: {error_msg}"
                    )
                
                # Extract SSO URL from response
                # The response should contain the hosted KYC URL
                kyc_url = (meon_data.get("sso_url") or meon_data.get("url") or 
                          meon_data.get("link") or meon_data.get("redirect_url") or
                          meon_data.get("data", {}).get("url"))
                kyc_id = (meon_data.get("request_id") or meon_data.get("id") or 
                         meon_data.get("kyc_id") or meon_data.get("session_id"))
                
                if not kyc_url:
                    logger.warning(f"Meon response missing SSO URL: {meon_data}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Meon API response missing SSO URL. Response: {meon_data}"
                    )
                
                # Update KYC request
                kyc_request.provider_kyc_id = kyc_id or str(kyc_request.id)
                kyc_request.status = "in_progress"
                if kyc_id:
                    artist.kyc_id = kyc_id
                
                db.commit()
                
                return {
                    "status": "initiated",
                    "kyc_url": kyc_url,
                    "kyc_id": kyc_id,
                    "message": "KYC initiated successfully. Redirect user to kyc_url"
                }
            else:
                logger.error(f"Meon API error response: {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Meon API error ({response.status_code}): {response.text[:200]}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Meon API timeout. Please try again.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to Meon API: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"KYC initiation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate KYC. Please try again later.")


@router.post("/kyc/face/{artist_id}")
async def start_face_verification(
    artist_id: str,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db)
):
    """
    Initiate face/liveness verification with Meon
    This should be called after document verification is complete
    Returns hosted URL for user to complete face verification
    """
    # Validate and find artist
    try:
        artist_uuid = uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artist ID format")
    
    artist = db.query(Artist).filter(Artist.id == artist_uuid).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Check if already fully verified
    if artist.kyc_verified:
        return {
            "status": "already_verified",
            "message": "KYC already fully verified",
            "kyc_verified": True
        }
    
    # Get the existing KYC request
    kyc_request = db.query(KYCRequest).filter(
        KYCRequest.artist_id == artist.id,
        KYCRequest.status.in_(["document_verified", "face_verification_pending"])
    ).order_by(KYCRequest.created_at.desc()).first()
    
    if not kyc_request:
        raise HTTPException(
            status_code=400,
            detail="Document verification must be completed first. Please complete Aadhar/PAN verification."
        )
    
    # Check if document is verified
    if not kyc_request.document_verified:
        return {
            "status": "document_pending",
            "message": "Document verification pending. Please complete Aadhar/PAN verification first.",
            "current_step": kyc_request.current_step
        }
    
    # Check if face is already verified
    if kyc_request.face_verified:
        return {
            "status": "face_already_verified",
            "message": "Face verification already completed",
            "kyc_verified": artist.kyc_verified
        }
    
    # Call Meon API to initiate face verification
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Meon SSO KYC Route API for face/liveness verification
            base_url = os.getenv('MEON_API_BASE_URL', 'https://live.meon.co.in')
            redirect_url = os.getenv('MEON_REDIRECT_URL', 'https://www.google.com')
            
            # Build request body for liveimage workflow
            request_body = {
                "company": os.getenv('MEON_COMPANY_NAME', 'mimora'),
                "workflowName": os.getenv('MEON_FACE_WORKFLOW_NAME', 'image_verification'),
                "secret_key": os.getenv('MEON_SECRET_KEY'),
                "notification": True,        
                "additional_info": {
                    "image_captured": ""  # Will be captured by Meon's flow
                },
                "unique_keys": {
                    "artist_id": str(artist.id),
                    "reference_id": str(kyc_request.id)
                },
                "is_redirect": True,
                "redirect_url": redirect_url,
            }
            
            meon_url = f"{base_url}/get_sso_kyc_route"
            logger.info(f"Calling Meon Face Verification API: {meon_url}")
            
            response = await client.post(
                meon_url,
                headers={"Content-Type": "application/json"},
                json=request_body
            )
            
            logger.info(f"Meon face response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                try:
                    if not response.text:
                        raise HTTPException(
                            status_code=500,
                            detail="Empty response from Meon API"
                        )
                    
                    meon_data = response.json()
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse face verification JSON: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid response from Meon API: {response.text[:100]}"
                    )
                
                # Check for API-level errors
                if meon_data.get("success") == False or meon_data.get("status") == False:
                    error_msg = meon_data.get("msg") or meon_data.get("message") or "Unknown error from Meon API"
                    logger.error(f"Meon face API error: {error_msg}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Meon API error: {error_msg}"
                    )
                
                # Extract SSO URL from response
                face_url = (meon_data.get("sso_url") or meon_data.get("url") or 
                          meon_data.get("link") or meon_data.get("redirect_url") or
                          meon_data.get("data", {}).get("url"))
                
                if not face_url:
                    logger.warning(f"Meon face response missing SSO URL: {meon_data}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Meon API response missing SSO URL. Response: {meon_data}"
                    )
                
                # Update KYC request status
                kyc_request.status = "face_verification_pending"
                kyc_request.updated_at = datetime.utcnow()
                db.commit()
                
                return {
                    "status": "initiated",
                    "face_url": face_url,
                    "kyc_id": str(kyc_request.provider_kyc_id),
                    "message": "Face verification initiated. Redirect user to face_url"
                }
            else:
                logger.error(f"Meon face API error response: {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Meon API error ({response.status_code}): {response.text[:200]}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Meon API timeout. Please try again.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to Meon API: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Face verification initiation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate face verification. Please try again later.")


@router.post("/kyc/webhook")
async def kyc_webhook(
    payload: dict,
    x_meon_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Meon to send KYC verification results.
    
    This handles the two-step verification flow:
    1. First callback: Aadhaar OR PAN verification complete
    2. Second callback: Face verification complete
    
    Expected payload structure (may vary based on Meon's workflow):
    {
        "request_id": "xxx" or "kyc_id": "xxx",
        "status": "success" | "failed" | "pending",
        "step": "aadhaar" | "pan" | "face" | "complete",
        "verification_type": "aadhaar" | "pan" | "face",
        "data": {
            "name": "...",
            "dob": "...",
            "aadhaar_number": "XXXX-XXXX-1234",
            ...
        },
        "unique_keys": {
            "mobile": "..."
        },
        "additional_info": {
            "artist_id": "...",
            "reference_id": "..."
        }
    }
    """
    
    # Log incoming webhook
    logger.info("KYC webhook received")
    
    # Verify webhook signature for security
    webhook_secret = os.getenv('MEON_WEBHOOK_SECRET')
    if webhook_secret:
        if not x_meon_signature:
            logger.error("Missing webhook signature header")
            raise HTTPException(status_code=403, detail="Missing webhook signature")
        
        expected_signature = hmac.HMAC(
            webhook_secret.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, x_meon_signature):
            logger.error("Invalid webhook signature")
            raise HTTPException(status_code=403, detail="Invalid webhook signature")
    
    # Extract KYC ID from various possible field names
    kyc_id = (
        payload.get("request_id") or 
        payload.get("kyc_id") or 
        payload.get("id") or
        payload.get("session_id") or
        payload.get("transaction_id")
    )
    
    # Extract reference from additional_info if present
    additional_info = payload.get("additional_info", {})
    reference_id = additional_info.get("reference_id")
    artist_id_from_payload = additional_info.get("artist_id")
    
    # Try to find KYC request by various methods
    kyc_request = None
    
    if kyc_id:
        kyc_request = db.query(KYCRequest).filter(
            KYCRequest.provider_kyc_id == kyc_id
        ).first()
    
    if not kyc_request and reference_id:
        try:
            ref_uuid = uuid.UUID(reference_id)
            kyc_request = db.query(KYCRequest).filter(
                KYCRequest.id == ref_uuid
            ).first()
        except ValueError:
            pass
    
    if not kyc_request:
        logger.error(f"KYC request not found for kyc_id: {kyc_id}, reference_id: {reference_id}")
        raise HTTPException(
            status_code=404,
            detail=f"KYC request not found. kyc_id: {kyc_id}, reference_id: {reference_id}"
        )
    
    # Find associated artist
    artist = db.query(Artist).filter(Artist.id == kyc_request.artist_id).first()
    if not artist:
        logger.error(f"Artist not found for KYC request: {kyc_request.id}")
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Extract status and verification type
    status = (
        payload.get("status") or 
        payload.get("verification_status") or
        "pending"
    ).lower()
    
    verification_type = (
        payload.get("verification_type") or 
        payload.get("step") or 
        payload.get("type") or
        "unknown"
    ).lower()
    
    # Extract verification data
    verification_data = payload.get("data", {}) or payload.get("verification_details", {}) or {}
    
    logger.info(f"Processing webhook: status={status}, type={verification_type}, artist={artist.id}")
    
    # Store the full payload for records
    existing_data = {}
    if kyc_request.verification_data:
        try:
            existing_data = json.loads(kyc_request.verification_data)
        except:
            existing_data = {}
    
    # Add this verification to the history
    if "verifications" not in existing_data:
        existing_data["verifications"] = []
    
    existing_data["verifications"].append({
        "type": verification_type,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "data": verification_data
    })
    existing_data["last_update"] = payload
    
    kyc_request.verification_data = json.dumps(existing_data)
    kyc_request.updated_at = datetime.utcnow()
    
    # Update verification status based on the step
    if status in ["success", "verified", "completed", "complete"]:
        if verification_type in ["aadhaar", "pan", "document", "id", "analyst"]:
            # Step 1 complete: Aadhaar or PAN verified
            kyc_request.document_verified = True
            kyc_request.current_step = "face"
            kyc_request.status = "document_verified"
            logger.info(f"Document verification complete for artist {artist.id} - Ready for face verification")
            
        elif verification_type in ["face", "liveness", "selfie", "photo", "liveimage"]:
            # Step 2 complete: Face verified - Full KYC complete!
            kyc_request.face_verified = True
            kyc_request.current_step = "complete"
            kyc_request.status = "verified"
            artist.kyc_verified = True
            logger.info(f"Face verification complete - KYC VERIFIED for artist {artist.id}")
            
        elif verification_type in ["complete", "all", "full"]:
            # Full workflow completed in one callback
            kyc_request.document_verified = True
            kyc_request.face_verified = True
            kyc_request.current_step = "complete"
            kyc_request.status = "verified"
            artist.kyc_verified = True
            logger.info(f"Full KYC VERIFIED for artist {artist.id}")
            
    elif status in ["failed", "rejected", "error"]:
        kyc_request.status = "failed"
        artist.kyc_verified = False
        logger.warning(f"Verification FAILED for artist {artist.id}: {verification_type}")
    
    else:
        # Status is pending or in_progress
        kyc_request.status = "in_progress"
        logger.info(f"Verification in progress for artist {artist.id}")
    
    # Update provider_kyc_id if we got a new one
    if kyc_id and not kyc_request.provider_kyc_id:
        kyc_request.provider_kyc_id = kyc_id
        artist.kyc_id = kyc_id
    
    db.commit()
    
    logger.info(f"Webhook processed: artist={artist.id}, status={kyc_request.status}, verified={artist.kyc_verified}")
    
    return {
        "success": True,
        "message": f"Webhook processed: {verification_type} - {status}",
        "artist_id": str(artist.id),
        "kyc_status": kyc_request.status,
        "kyc_verified": artist.kyc_verified,
        "document_verified": kyc_request.document_verified,
        "face_verified": kyc_request.face_verified,
        "current_step": kyc_request.current_step
    }


@router.get("/kyc/status/{artist_id}")
async def get_kyc_status(
    artist_id: str,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db)
):
    """
    Get current KYC verification status for an artist
    """
    # Validate and find artist
    try:
        artist_uuid = uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artist ID format")
    
    artist = db.query(Artist).filter(Artist.id == artist_uuid).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Get latest KYC request
    kyc_request = db.query(KYCRequest).filter(
        KYCRequest.artist_id == artist.id
    ).order_by(KYCRequest.created_at.desc()).first()
    
    response = {
        "artist_id": str(artist.id),
        "username": artist.username,
        "kyc_verified": artist.kyc_verified,
        "bank_verified": artist.bank_verified,
        "kyc_status": kyc_request.status if kyc_request else "not_started",
        "kyc_id": artist.kyc_id,
        "document_verified": kyc_request.document_verified if kyc_request else False,
        "face_verified": kyc_request.face_verified if kyc_request else False,
        "current_step": kyc_request.current_step if kyc_request else "document"
    }
    
    # Add verification details if available
    if kyc_request and kyc_request.verification_data:
        try:
            verification_data = json.loads(kyc_request.verification_data)
            response["verification_details"] = verification_data.get("verification_details", {})
            response["last_updated"] = kyc_request.updated_at.isoformat()
        except:
            pass
    
    return response


@router.post("/kyc/retry/{artist_id}")
async def retry_kyc(
    artist_id: str,
    current_artist: Artist = Depends(get_current_artist),
    db: Session = Depends(get_db)
):
    """
    Retry KYC verification if previous attempt failed
    """
    try:
        artist_uuid = uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artist ID format")
    
    artist = db.query(Artist).filter(Artist.id == artist_uuid).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Mark previous KYC requests as cancelled
    db.query(KYCRequest).filter(
        KYCRequest.artist_id == artist.id,
        KYCRequest.status.in_(["pending", "in_progress", "failed"])
    ).update({"status": "cancelled"})
    
    # Reset artist KYC status (only KYC, not bank verification)
    artist.kyc_verified = False
    artist.kyc_id = None
    
    db.commit()
    
    # Initiate new KYC (reuse start_kyc logic)
    return await start_kyc(artist_id, current_artist, db)


# Add this temporary debugging function at the top of the file
async def test_meon_endpoints():
    """
    Test various possible Meon API endpoints to find the correct one
    """
    import httpx
    
    possible_endpoints = [
        "/kyc/start",
        "/kyc/initiate", 
        "/kyc/init",
        "/verify/start",
        "/verify/initiate",
        "/verify/init",
        "/api/kyc/start",
        "/api/verify/initiate",
        "/start",
        "/initiate",
        ""  # Just base URL
    ]
    
    base_url = os.getenv('MEON_API_BASE_URL', 'https://kyc.meon.co.in/api')
    api_key = os.getenv('MEON_API_KEY')
    
    print(f"\n=== Testing Meon API Endpoints ===")
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:20] if api_key else 'NOT SET'}...")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for endpoint in possible_endpoints:
            full_url = f"{base_url}{endpoint}"
            try:
                # Try GET first
                response = await client.get(
                    full_url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                print(f"GET {endpoint}: {response.status_code}")
                
                # Try POST
                response = await client.post(
                    full_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={"test": "data"}
                )
                print(f"POST {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"{endpoint}: ERROR - {str(e)}")
    
    print("=" * 50 + "\n")


# Add this route to test endpoints
@router.get("/kyc/test-endpoints")
async def test_endpoints():
    """Temporary endpoint to test Meon API endpoints"""
    await test_meon_endpoints()
    return {"message": "Check server logs for endpoint test results"}


# ============ PROFILE COMPLETION ENDPOINT ============

@router.put("/auth/artist/profile", response_model=ArtistResponse)
async def complete_artist_profile(
    request: Request,
    payload: ArtistProfileCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    Complete artist profile after initial signup
    Receives Firebase Storage URLs from frontend
    """
    try:
        # Get current artist from Firebase token
        artist = await get_current_artist(request, db)
        
        # Update personal details
        if payload.name:
            artist.name = payload.name
        if payload.username:
            artist.username = payload.username
        if payload.phone_number:
            artist.phone_number = payload.phone_number
        if payload.birthdate:
            # Convert DD/MM/YYYY to datetime
            from datetime import datetime
            artist.birthdate = datetime.strptime(payload.birthdate, "%d/%m/%Y")
        if payload.gender:
            artist.gender = payload.gender
        if payload.experience:
            artist.experience = payload.experience
        if payload.bio:
            artist.bio = payload.bio
        
        # Update file URLs (from Firebase Storage)
        if payload.profile_pic_url:
            artist.profile_pic_url = payload.profile_pic_url
        if payload.certificate_url:
            artist.certificate_url = payload.certificate_url
        
        # Update professional info
        if payload.how_did_you_learn:
            artist.how_did_you_learn = payload.how_did_you_learn
        if payload.profession:
            artist.profession = payload.profession
        
        # Update address
        if payload.flat_building:
            artist.flat_building = payload.flat_building
        if payload.street_area:
            artist.street_area = payload.street_area
        if payload.landmark:
            artist.landmark = payload.landmark
        if payload.pincode:
            artist.pincode = payload.pincode
        if payload.city:
            artist.city = payload.city
        if payload.state:
            artist.state = payload.state
        if payload.latitude and payload.longitude:
            artist.latitude = payload.latitude
            artist.longitude = payload.longitude
            # Build address string
            address_parts = [p for p in [payload.flat_building, payload.street_area, payload.landmark, payload.city, payload.state, payload.pincode] if p]
            artist.address = ", ".join(address_parts)
            # Update PostGIS geometry
            artist.location = f"POINT({payload.longitude} {payload.latitude})"
        # Only mark profile as completed when all steps are done
        if payload.mark_complete:
            artist.profile_completed = True
        
        db.commit()
        db.refresh(artist)
        
        return artist
        
    except Exception as e:
        db.rollback()
        print(f"ERROR completing profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

