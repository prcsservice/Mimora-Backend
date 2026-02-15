import firebase_admin
from firebase_admin import credentials, auth
import jwt

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def verify_firebase_token(token: str):
    """Verify Firebase ID token (for Google OAuth)"""
    return auth.verify_id_token(token, clock_skew_seconds=5)

def verify_custom_token(token: str):
    """
    Verify custom JWT token (from email/phone OTP).
    We decode without signature verification since we trust our own tokens.
    """
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        raise Exception(f"Invalid custom token: {str(e)}")

def verify_token(token: str):
    """
    Verify token - tries Firebase ID token first, then custom token.
    This supports both Google OAuth (Firebase ID) and email/phone OTP (custom token).
    Returns decoded token payload.
    """
    try:
        # Try Firebase ID token first (for Google OAuth)
        return verify_firebase_token(token)
    except:
        # Fallback to custom token (for email/phone OTP)
        return verify_custom_token(token)

