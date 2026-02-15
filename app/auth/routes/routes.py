from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.params import Header
from sqlalchemy.orm import Session
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter for this router
limiter = Limiter(key_func=get_remote_address)

from app.auth.firebase import verify_firebase_token
from app.auth.schemas import EmailSignupRequest, OAuthRequest, OTPRequest, VerifyOTPRequest, UserResponse, CheckUserRequest, EmailLoginRequest, UserLocationUpdate
from app.auth.models import User, EmailOTP, Artist
from app.auth.database import get_db
from app.auth.utils.otp import generate_otp, hash_otp, verify_otp, otp_expiry
from app.auth.utils.send_email import send_otp_email
import firebase_admin
from firebase_admin import auth as firebase_auth
from app.auth.utils.current_user import get_current_user

router = APIRouter()


@router.get("/auth/customer/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/auth/customer/location", response_model=UserResponse)
async def update_location(
    payload: UserLocationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update authenticated user's location and address
    """
    current_user.latitude = payload.latitude
    current_user.longitude = payload.longitude
    current_user.flat_building = payload.flat_building
    current_user.street_area = payload.street_area
    current_user.landmark = payload.landmark
    current_user.pincode = payload.pincode
    current_user.city = payload.city
    current_user.state = payload.state
    
    # Build full address string
    address_parts = [p for p in [payload.flat_building, payload.street_area, payload.landmark, payload.city, payload.state, payload.pincode] if p]
    current_user.address = ", ".join(address_parts)
    
    # Update PostGIS geometry column
    # Point(longitude latitude)
    current_user.location = f"POINT({payload.longitude} {payload.latitude})"
    
    db.commit()
    db.refresh(current_user)
    
    return current_user



@router.post("/auth/customer/check")
async def check_user_exists(
    payload: CheckUserRequest,
    db: Session = Depends(get_db)
):
    """
    Check if a user exists without creating or modifying anything.
    Used by frontend to distinguish login vs signup flows.
    """
    from app.auth.schemas import CheckUserResponse
    
    if payload.type == "email":
        user = db.query(User).filter(User.email == payload.identifier).first()
    elif payload.type == "phone":
        user = db.query(User).filter(User.phone_number == payload.identifier).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid type. Use 'email' or 'phone'")
    
    return CheckUserResponse(
        exists=user is not None,
        user_type="customer" if user else None
    )


@router.post("/auth/customer/oauth", response_model=UserResponse)
@limiter.limit("20/minute")  # Rate limit for OAuth login
async def oauth_login(
    request: Request,
    payload: OAuthRequest = OAuthRequest(),
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
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        # Existing user - update if needed
        updated = False
        
        if user.firebase_uid != firebase_uid:
            user.firebase_uid = firebase_uid
            updated = True
        
        if user.provider != provider:
            user.provider = provider
            updated = True
        
        # Update name if provided and different
        # if name and user.name != name:
        #     user.name = name
        #     updated = True
        
        if updated:
            db.commit()
            db.refresh(user)
    else:
        # NEW: Check if email exists as Artist (prevent cross-account duplicates)
        existing_artist = db.query(Artist).filter(Artist.email == email).first()
        if existing_artist:
            raise HTTPException(
                status_code=400,
                detail="This email is registered as an artist account. Please use the artist login."
            )
        
        # New user - create
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name,
            provider=provider,
            latitude=payload.latitude,
            longitude=payload.longitude
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user






@router.post("/auth/customer/login", response_model=UserResponse)
@limiter.limit("20/minute")  # Rate limit for login attempts
async def login(
    request: Request,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split(" ")[1]
    decoded = verify_firebase_token(token)

    firebase_uid = decoded["uid"]
    email = decoded.get("email")
    name = decoded.get("name")
    provider = decoded["firebase"]["sign_in_provider"]

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    user = db.query(User).filter(User.email == email).first()

    if user:
        if user.firebase_uid != firebase_uid:
            user.firebase_uid = firebase_uid
            user.provider = provider
            db.commit()
    else:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name,
            provider=provider
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user   # SQLAlchemy → Pydantic auto converts


# @router.post("/auth/customer/email",response_model=UserResponse)
# async def emailLogin(
    
#     )


@router.post("/auth/customer/email")
@limiter.limit("5/minute")  # Strict limit to prevent OTP spam
async def email_signup(
    request: Request,
    payload: EmailSignupRequest,
    db: Session = Depends(get_db)
):

    # Delete expired OTPs for this email
    expired_otps = db.query(EmailOTP).filter(
        EmailOTP.email == payload.email,
        EmailOTP.expires_at < datetime.utcnow()
    ).all()
    
    if expired_otps:
        for expired_otp in expired_otps:
            db.delete(expired_otp)
        db.commit()
        print(f"Deleted {len(expired_otps)} expired OTP(s) for {payload.email}")
    # 1️⃣ Generate OTP
    otp = generate_otp()

    # 2️⃣ Store OTP + username
    otp_entry = EmailOTP(
        email=payload.email,
        username=payload.username,
        otp_hash=hash_otp(otp),
        expires_at=otp_expiry()
    )

    db.add(otp_entry)
    db.commit()

    # 3️⃣ Send OTP email
    send_otp_email(payload.email, otp)




@router.post("/auth/customer/email/login")
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
    # Check if user exists
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered. Please signup first.")
        # Delete expired OTPs for this email
    expired_otps = db.query(EmailOTP).filter(
        EmailOTP.email == payload.email,
        EmailOTP.expires_at < datetime.utcnow()
    ).all()
    
    if expired_otps:
        for expired_otp in expired_otps:
            db.delete(expired_otp)
        db.commit()
        print(f"Deleted {len(expired_otps)} expired OTP(s) for {payload.email}")
    # 1️⃣ Generate OTP
    otp = generate_otp()
    # Generate OTP
    otp = generate_otp()
    
    # Store OTP with existing username
    otp_entry = EmailOTP(
        email=payload.email,
        username=user.name,
        otp_hash=hash_otp(otp),
        expires_at=otp_expiry()
    )
    db.add(otp_entry)
    db.commit()
    
    # Send OTP email
    print(f"DEBUG OTP: {otp}")
    send_otp_email(payload.email, otp)
    
    return {"message": "OTP sent to your email", "email": payload.email}


@router.post("/auth/customer/email/verify", response_model=UserResponse)
@limiter.limit("10/minute")  # Prevent brute-force OTP guessing
async def verify_email_otp(
    request: Request,
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    # 1️⃣ Get the latest OTP record for this email
    otp_record = (
        db.query(EmailOTP)
        .filter(EmailOTP.email == payload.email)
        .order_by(EmailOTP.id.desc())
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
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        # 7️⃣ Create user in Firebase
        try:
            firebase_user = firebase_auth.create_user(
                email=payload.email,
                display_name=username
            )
        except firebase_auth.EmailAlreadyExistsError:
            firebase_user = firebase_auth.get_user_by_email(payload.email)

        # 8️⃣ Create user in DB
        user = User(
            email=payload.email,
            name=username,
            provider="email",
            firebase_uid=firebase_user.uid,
            city="",
            address=""
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
        print(f"DEBUG: generated custom_token: {custom_token[:10]}...") 
    except Exception as e:
        print(f"Error generating custom token: {e}")

    print(f"DEBUG: Returning user object with token field: {getattr(user, 'token', 'NOT SET')}")
    return user




@router.post("/auth/customer/otp", response_model=UserResponse)
@limiter.limit("10/minute")  # Rate limit for OTP authentication
async def otp_auth(
    request: Request,
    payload: OTPRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Authenticate user with Firebase OTP
    
    Process:
    1. Verify Firebase token from Authorization header
    2. Extract phone number from verified token
    3. Check if user exists
    4. Update or create user
    5. Return user data
    """
    
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
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")
    
    # Extract data from decoded token
    phone_number = decoded.get("phone_number")
    firebase_uid = decoded.get("uid")
    provider = decoded.get("firebase", {}).get("sign_in_provider", "phone")
    
    # Validate phone number exists
    if not phone_number:
        raise HTTPException(
            status_code=400, 
            detail="Phone number not found in Firebase token. Ensure phone authentication was used."
        )
    
    if not firebase_uid:
        raise HTTPException(status_code=400, detail="Firebase UID not found in token")
    
    # Check if user exists
    user = db.query(User).filter(User.phone_number == phone_number).first()
    
    if user:
        # Existing user - update if needed
        updated = False
        
        if user.firebase_uid != firebase_uid:
            user.firebase_uid = firebase_uid
            updated = True
        
        if user.provider != provider:
            user.provider = provider
            updated = True
        
        # Update name if provided and different
        if payload.name and user.name != payload.name:
            user.name = payload.name
            updated = True
        
        if updated:
            db.commit()
            db.refresh(user)
    else:
        # New user - create
        user = User(
            firebase_uid=firebase_uid,
            name=payload.name,
            phone_number=phone_number,
            provider=provider,
            latitude=payload.latitude,
            longitude=payload.longitude
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user










