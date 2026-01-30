"""
Complete Backend KYC Implementation - Routes
app/auth/routes.py
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import uuid
import httpx
import os
import hmac
import hashlib
import json

from app.auth.database import get_db
from app.auth.models import Artist, KYCRequest
from app.auth.schemas import ArtistCreate, ArtistResponse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Debug: Print loaded variables
print(f"DEBUG - MEON_API_BASE_URL: {os.getenv('MEON_API_BASE_URL')}")
print(f"DEBUG - MEON_API_KEY: {os.getenv('MEON_API_KEY')}")

router = APIRouter()


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
    existing = db.query(Artist).filter(Artist.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    
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


@router.post("/kyc/start/{artist_id}")
async def start_kyc(
    artist_id: str,
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
    
    # Call Meon API to initiate KYC
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Meon SSO Link API for hosted KYC verification
            # Endpoint: POST https://live.meon.co.in/get_sso_route
            base_url = os.getenv('MEON_API_BASE_URL', 'https://live.meon.co.in')
            
            # Build SSO request body per Meon documentation
            request_body = {
                "company": os.getenv('MEON_COMPANY_NAME', 'Mimora'),
                "workflowName": os.getenv('MEON_WORKFLOW_NAME'),  # Required - set in .env
                "secret_key": os.getenv('MEON_API_KEY'),
                "notification": True,
                "unique_keys": {
                    "mobile": artist.phone_number or ""
                },
                "additional_info": {
                    "artist_id": str(artist.id),
                    "email": artist.email,
                    "reference_id": str(kyc_request.id)
                }
            }
            
            # Validate required fields
            if not request_body["workflowName"]:
                raise HTTPException(
                    status_code=500,
                    detail="MEON_WORKFLOW_NAME environment variable not set. Please configure your Meon workflow name."
                )
            
            meon_url = f"{base_url}/get_sso_route"
            print(f"DEBUG - Calling Meon SSO API: {meon_url}")
            print(f"DEBUG - Request body: {request_body}")
            
            response = await client.post(
                meon_url,
                headers={"Content-Type": "application/json"},
                json=request_body
            )
            
            print(f"DEBUG - Meon response status: {response.status_code}")
            print(f"DEBUG - Meon response body: {response.text}")
            
            if response.status_code in [200, 201]:
                try:
                    if not response.text:
                        raise HTTPException(
                            status_code=500,
                            detail="Empty response from Meon API"
                        )
                    
                    meon_data = response.json()
                except json.JSONDecodeError:
                    print(f"DEBUG - Failed to parse JSON response: {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid response from Meon API: {response.text[:100]}"
                    )
                
                # Check for API-level errors
                if meon_data.get("success") == False or meon_data.get("status") == False:
                    error_msg = meon_data.get("msg") or meon_data.get("message") or "Unknown error from Meon API"
                    print(f"DEBUG - Meon API error: {error_msg}")
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
                    print(f"DEBUG - Full Meon response: {meon_data}")
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
                print(f"DEBUG - Meon API error response: {response.text}")
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
        print(f"KYC initiation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate KYC. Please try again later.")


@router.post("/kyc/webhook")
async def kyc_webhook(
    payload: dict,
    x_meon_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Meon to send KYC verification results
    
    Expected payload:
    {
        "kyc_id": "meon_xxx",
        "status": "verified" | "failed" | "pending",
        "client_reference_id": "uuid",
        "verification_details": {
            "aadhaar": {"verified": true, "name": "...", "dob": "..."},
            "face": {"verified": true, "confidence": 0.95},
            "bank": {"verified": true, "account_holder": "..."}
        },
        "timestamp": "2026-01-28T10:00:00Z"
    }
    """
    
    # Verify webhook signature for security
    if x_meon_signature and os.getenv('MEON_WEBHOOK_SECRET'):
        expected_signature = hmac.new(
            os.getenv('MEON_WEBHOOK_SECRET').encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, x_meon_signature):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")
    
    # Extract data from payload
    kyc_id = payload.get("kyc_id")
    status = payload.get("status")
    
    if not kyc_id:
        raise HTTPException(status_code=400, detail="Missing kyc_id in payload")
    
    # Find KYC request
    kyc_request = db.query(KYCRequest).filter(
        KYCRequest.provider_kyc_id == kyc_id
    ).first()
    
    if not kyc_request:
        raise HTTPException(
            status_code=404,
            detail=f"KYC request not found for kyc_id: {kyc_id}"
        )
    
    # Update KYC request
    kyc_request.status = status
    kyc_request.verification_data = json.dumps(payload)
    kyc_request.updated_at = datetime.utcnow()
    
    # Find and update artist
    artist = db.query(Artist).filter(
        Artist.id == kyc_request.artist_id
    ).first()
    
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Update artist verification status based on Meon response
    verification_details = payload.get("verification_details", {})
    
    if status == "verified":
        # Check individual verifications
        aadhaar_verified = verification_details.get("aadhaar", {}).get("verified", False)
        face_verified = verification_details.get("face", {}).get("verified", False)
        bank_verified = verification_details.get("bank", {}).get("verified", False)
        
        # Update artist
        artist.kyc_verified = aadhaar_verified and face_verified
        artist.bank_verified = bank_verified
        
    elif status == "failed":
        artist.kyc_verified = False
        artist.bank_verified = False
    
    db.commit()
    
    # Log the webhook (use your logging system)
    print(f"KYC webhook received - Artist: {artist.id}, Status: {status}")
    
    return {
        "success": True,
        "message": f"KYC status updated to {status}",
        "artist_id": str(artist.id),
        "kyc_verified": artist.kyc_verified,
        "bank_verified": artist.bank_verified
    }


@router.get("/kyc/status/{artist_id}")
async def get_kyc_status(
    artist_id: str,
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
        "kyc_id": artist.kyc_id
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
    
    # Reset artist KYC status
    artist.kyc_verified = False
    artist.bank_verified = False
    artist.kyc_id = None
    
    db.commit()
    
    # Initiate new KYC (reuse start_kyc logic)
    return await start_kyc(artist_id, db)


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