"""
Utility to get the current authenticated user from Firebase token.

Usage in routes:
    from app.auth.utils.current_user import get_current_user
    
    @router.get("/me")
    async def get_me(current_user: User = Depends(get_current_user)):
        return current_user
"""

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.auth.firebase import verify_token
from app.auth.database import get_db
from app.auth.models import User


async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI Dependency to get the current authenticated user.
    
    Process:
    1. Extract Bearer token from Authorization header
    2. Verify token with Firebase
    3. Search for user in database by firebase_uid
    4. Return user data to frontend
    
    Raises:
        HTTPException 401: Invalid/missing token
        HTTPException 404: User not found in database
    """
    
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = authorization.split(" ")[1]
    
    # Verify token (handles both Firebase ID and custom tokens)
    try:
        decoded = verify_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token verification failed: {str(e)}"
        )
    
    # Get firebase_uid from decoded token
    firebase_uid = decoded.get("uid")
    
    if not firebase_uid:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: Firebase UID not found"
        )
    
    # Search for user in database
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    
    # Also try email/phone if provided in token (for robustness)
    if not user and (decoded.get("email") or decoded.get("phone_number")):
        if decoded.get("email"):
            user = db.query(User).filter(User.email == decoded.get("email")).first()
        if not user and decoded.get("phone_number"):
            user = db.query(User).filter(User.phone_number == decoded.get("phone_number")).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found. Please sign up first."
        )
    
    return user


async def get_current_artist(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    FastAPI Dependency to get the current authenticated artist.
    Similar to get_current_user but searches in the Artist table.
    """
    from app.auth.models import Artist
    
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = authorization.split(" ")[1]
    
    
    # Verify token (handles both Firebase ID and custom tokens)
    try:
        decoded = verify_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token verification failed: {str(e)}"
        )
    
    # Get email/phone from decoded token to search artist
    firebase_uid = decoded.get("uid")
    email = decoded.get("email")
    phone = decoded.get("phone_number")
    
    if not firebase_uid:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: Firebase UID not found"
        )
    
    # Search for artist by firebase_uid first (most reliable)
    artist = db.query(Artist).filter(Artist.firebase_uid == firebase_uid).first()
    
    # Fallback to email or phone if firebase_uid lookup failed
    if not artist and email:
        artist = db.query(Artist).filter(Artist.email == email).first()
    if not artist and phone:
        artist = db.query(Artist).filter(Artist.phone_number == phone).first()
    
    if not artist:
        raise HTTPException(
            status_code=404,
            detail="Artist not found. Please register as an artist first."
        )
    
    return artist
