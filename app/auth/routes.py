from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Header
from sqlalchemy.orm import Session
from datetime import datetime

from app.auth.firebase import verify_firebase_token
from app.auth.schemas import EmailSignupRequest, OTPRequest, VerifyOTPRequest, UserResponse
from app.auth.models import User, EmailOTP
from app.auth.database import get_db
from app.auth.utils.otp import generate_otp, hash_otp, verify_otp, otp_expiry
from app.auth.utils.send_email import send_otp_email
import firebase_admin
from firebase_admin import auth as firebase_auth


router = APIRouter()

@router.post("/auth/customer/oauth", response_model=UserResponse)
async def oauth_login(
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
        if name and user.name != name:
            user.name = name
            updated = True
        
        if updated:
            db.commit()
            db.refresh(user)
    else:
        # New user - create
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name,
            provider=provider
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user






@router.post("/auth/customer/login", response_model=UserResponse)
async def login(
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
async def email_signup(
    payload: EmailSignupRequest,
    db: Session = Depends(get_db)
):
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

    return {"message": "OTP sent to email"}




@router.post("/auth/customer/email/verify", response_model=UserResponse)
async def verify_email_otp(
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
        raise HTTPException(status_code=400, detail="OTP not found")

    # 2️⃣ Check expiry
    if otp_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    # 3️⃣ Verify OTP
    if not verify_otp(payload.otp, otp_record.otp_hash):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # 4️⃣ Get the username from OTP record
    username = otp_record.username

    # 5️⃣ Check if user already exists
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        # 6️⃣ Create user in Firebase
        try:
            firebase_user = firebase_auth.create_user(
                email=payload.email,
                display_name=username
            )
        except firebase_auth.EmailAlreadyExistsError:
            firebase_user = firebase_auth.get_user_by_email(payload.email)

        # 7️⃣ Create user in DB
        user = User(
            email=payload.email,
            name=username,
            provider="email",
            firebase_uid=firebase_user.uid
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user




@router.post("/auth/customer/otp", response_model=UserResponse)
async def otp_auth(
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
            provider=provider
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user










