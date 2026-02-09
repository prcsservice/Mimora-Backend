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
from app.auth.utils.current_user import get_current_artist
# Load environment variables from .env file
load_dotenv()

# # Debug: Print loaded variables
# print(f"DEBUG - MEON_API_BASE_URL: {os.getenv('MEON_API_BASE_URL')}")
# print(f"DEBUG - MEON_API_KEY: {os.getenv('MEON_API_KEY')}")

router = APIRouter()




@router.get("/auth/artist/me")
async def get_artist_profile(artist: Artist = Depends(get_current_artist)):
    return artist

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
    
    # Call Meon API to initiate Aadhar/PAN verification
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Meon SSO KYC Route API for Aadhar/PAN verification
            # Endpoint: POST https://ipo.meon.co.in/get_sso_kyc_route
            base_url = os.getenv('MEON_API_BASE_URL', 'https://live.meon.co.in/get_sso_route')
            
            # Build request body per Meon documentation for analyst workflow
            request_body = {
                "company": os.getenv('MEON_COMPANY_NAME', 'mimora'),
                "workflowName": os.getenv('MEON_KYC_WORKFLOW_NAME', 'analyst'),
                "notification": True,
                "secret_key": os.getenv('MEON_SECRET_KEY'),
                "unique_keys": {
                    "artist_id": str(artist.id),
                    "reference_id": str(kyc_request.id)
                },
                "is_redirect" : true,
                "redirect_url" : "https://www.google.com",

                
            }
            
            meon_url = f"{base_url}/get_sso_kyc_route"
            print(f"DEBUG - Calling Meon SSO KYC API: {meon_url}")
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


@router.post("/kyc/face/{artist_id}")
async def start_face_verification(
    artist_id: str,
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
        KYCRequest.status.in_(["document_verified", "in_progress"])
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
            # Endpoint: POST https://ipo.meon.co.in/get_sso_kyc_route
            base_url = os.getenv('MEON_API_BASE_URL', 'https://live.meon.co.in/get_sso_route')
            
            # Build request body for liveimage workflow
            request_body = {
                "company": os.getenv('MEON_COMPANY_NAME', 'mimora'),
                "workflowName": os.getenv('MEON_FACE_WORKFLOW_NAME', 'image_verification'),
                "notification": True,
                "secret_key": os.getenv('MEON_SECRET_KEY'),
                "additional_info": {
                    "image_captured": ""  # Will be captured by Meon's flow
                },
                "unique_keys": {
                    "artist_id": str(artist.id),
                    "reference_id": str(kyc_request.id)
                },
                "is_redirect" : true,
                "redirect_url" : "https://www.google.com",
            }
            
            meon_url = f"{base_url}/get_sso_kyc_route"
            print(f"DEBUG - Calling Meon Face Verification API: {meon_url}")
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
                face_url = (meon_data.get("sso_url") or meon_data.get("url") or 
                          meon_data.get("link") or meon_data.get("redirect_url") or
                          meon_data.get("data", {}).get("url"))
                
                if not face_url:
                    print(f"DEBUG - Full Meon response: {meon_data}")
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
        print(f"Face verification initiation error: {str(e)}")
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
    
    # Log incoming webhook for debugging
    print(f"=== KYC WEBHOOK RECEIVED ===")
    print(f"Payload: {json.dumps(payload, indent=2, default=str)}")
    print(f"Signature: {x_meon_signature}")
    
    # Verify webhook signature for security (if configured)
    if x_meon_signature and os.getenv('MEON_WEBHOOK_SECRET'):
        expected_signature = hmac.new(
            os.getenv('MEON_WEBHOOK_SECRET').encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, x_meon_signature):
            print(f"ERROR - Invalid webhook signature")
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
        print(f"ERROR - KYC request not found for kyc_id: {kyc_id}, reference_id: {reference_id}")
        raise HTTPException(
            status_code=404,
            detail=f"KYC request not found. kyc_id: {kyc_id}, reference_id: {reference_id}"
        )
    
    # Find associated artist
    artist = db.query(Artist).filter(Artist.id == kyc_request.artist_id).first()
    if not artist:
        print(f"ERROR - Artist not found for KYC request: {kyc_request.id}")
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
    
    print(f"Processing: status={status}, type={verification_type}, artist={artist.id}")
    
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
            print(f"Document verification complete for artist {artist.id} - Ready for face verification")
            
        elif verification_type in ["face", "liveness", "selfie", "photo", "liveimage"]:
            # Step 2 complete: Face verified - Full KYC complete!
            kyc_request.face_verified = True
            kyc_request.current_step = "complete"
            kyc_request.status = "verified"
            artist.kyc_verified = True
            print(f"Face verification complete - KYC VERIFIED for artist {artist.id}")
            
        elif verification_type in ["complete", "all", "full"]:
            # Full workflow completed in one callback
            kyc_request.document_verified = True
            kyc_request.face_verified = True
            kyc_request.current_step = "complete"
            kyc_request.status = "verified"
            artist.kyc_verified = True
            print(f"Full KYC VERIFIED for artist {artist.id}")
            
    elif status in ["failed", "rejected", "error"]:
        kyc_request.status = "failed"
        artist.kyc_verified = False
        print(f"Verification FAILED for artist {artist.id}: {verification_type}")
    
    else:
        # Status is pending or in_progress
        kyc_request.status = "in_progress"
        print(f"Verification in progress for artist {artist.id}")
    
    # Update provider_kyc_id if we got a new one
    if kyc_id and not kyc_request.provider_kyc_id:
        kyc_request.provider_kyc_id = kyc_id
        artist.kyc_id = kyc_id
    
    db.commit()
    
    print(f"=== WEBHOOK PROCESSED ===")
    print(f"Artist: {artist.id}, KYC Status: {kyc_request.status}, KYC Verified: {artist.kyc_verified}")
    print(f"Document Verified: {kyc_request.document_verified}, Face Verified: {kyc_request.face_verified}")
    
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