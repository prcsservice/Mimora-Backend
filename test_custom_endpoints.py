
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def check_custom_endpoints():
    endpoints = [
        "https://live.meon.co.in/api/kyc/start",
        "https://live.meon.co.in/api/verify/initiate"
    ]
    
    api_key = os.getenv('MEON_API_KEY')
    print(f"API Key: {api_key[:10]}...")
    
    # Try different auth headers - the key looks odd
    auth_Headers = [
        {"Authorization": f"Bearer {api_key}"},
        {"Authorization": api_key},
        {"x-api-key": api_key},
        {"Authorization": f"Basic {api_key}"} # Unlikely if it's that long
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in endpoints:
            print(f"\nChecking {url}...")
            
            # GET request
            try:
                response = await client.get(
                   url,
                   headers={"Authorization": f"Bearer {api_key}"}
                )
                print(f"GET Status: {response.status_code}")
                if response.status_code == 400:
                    print(f"GET Body: {response.text[:500]}")
                print(f"GET Headers: {response.headers}")
            except Exception as e:
                print(f"GET Error: {e}")
                
            # POST request with different Auth
            print("Checking POST with auth variations...")
            for i, headers in enumerate(auth_Headers):
                try:
                    h = headers.copy()
                    h["Content-Type"] = "application/json"
                    response = await client.post(
                        url,
                        headers=h,
                        json={"test": "data"}
                    )
                    if response.status_code != 405:
                        print(f"POST {i} {url}: {response.status_code}")
                        print(f"Header used: {list(headers.keys())[0]}")
                        print(f"Body: {response.text[:200]}")
                except Exception as e:
                    print(f"POST Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_custom_endpoints())
