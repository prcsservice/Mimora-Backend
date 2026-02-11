import requests
import json
import time

BASE_URL = "http://localhost:8000"
EMAIL = f"testuser_{int(time.time())}@example.com"
USERNAME = "Test Loctest"

def run_verification():
    print(f"Starting verification for {EMAIL}")
    
    # 1. Signup
    print("1. Signing up...")
    resp = requests.post(f"{BASE_URL}/auth/customer/email", json={"email": EMAIL, "username": USERNAME})
    if resp.status_code != 200:
        print(f"Signup failed: {resp.text}")
        return
    
    otp = resp.json().get("otp")
    print(f"Got OTP: {otp}")
    
    # 2. Verify OTP and get Token
    print("2. Verifying OTP...")
    resp = requests.post(f"{BASE_URL}/auth/customer/email/verify", json={"email": EMAIL, "otp": otp})
    if resp.status_code != 200:
        print(f"OTP verification failed: {resp.text}")
        return
        
    user_data = resp.json()
    token = user_data.get("token")
    # Actually the token is returned in the user object IF mock verification works?
    # Wait, in verify_email_otp:
    # user.token = custom_token
    # return user
    # So yes, token is in response.
    
    # However, verify_firebase_token checks real firebase tokens?
    # verify_firebase_token is imported from app.auth.firebase
    # If the token is a custom token, verify_firebase_token might fail if it expects an ID token.
    # Custom tokens are for signing in on the client side. ID tokens are what execute requests.
    # This might be tricky.
    # Let's check verify_firebase_token implementation.
    
    print(f"Got Token: {token[:10]}...") 
    
    # If verify_firebase_token validates ID tokens, then passing a custom token will fail.
    # But let's try.
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Update Location
    print("3. Updating Location...")
    lat = 12.9716
    lon = 77.5946
    resp = requests.put(f"{BASE_URL}/auth/customer/location", json={"latitude": lat, "longitude": lon}, headers=headers)
    
    if resp.status_code == 401:
        print("Unauthorized. Custom token probably not accepted as ID token.")
        # Attempt login flow is mocked?
        # If verify_firebase_token fails, we can't proceed easily without client SDK.
        # But we can check if I can mock verify_firebase_token temporarily in the code.
        return

    if resp.status_code != 200:
        print(f"Location update failed: {resp.text}")
        return
        
    print("Location update successful!")
    print(resp.json())
    
    # 4. Verify Update
    print("4. Verifying via GET /me ...")
    resp = requests.get(f"{BASE_URL}/auth/customer/me", headers=headers)
    if resp.status_code == 200:
        user = resp.json()
        if user['latitude'] == lat and user['longitude'] == lon:
            print("SUCCESS: Location verified!")
        else:
            print(f"FAILURE: Location mismatch. Expected {lat},{lon}. Got {user['latitude']},{user['longitude']}")
    else:
        print(f"GET /me failed: {resp.text}")

if __name__ == "__main__":
    run_verification()
