
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def test_variations():
    base_url = "https://live.meon.co.in/api/kyc/start"
    api_key = os.getenv('MEON_API_KEY')
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    print(f"Testing {base_url} variations...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. GET with query params
        print("\n1. GET withQueryParams:")
        try:
            resp = await client.get(base_url, params={"key": api_key, "ref": "test1234"}, headers=headers)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

        # 2. POST with application/x-www-form-urlencoded
        print("\n2. POST form-urlencoded:")
        try:
            resp = await client.post(base_url, data={"key": api_key}, headers=headers)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

        # 3. POST with explicit JSON (should be 405 based on history, but verifying)
        print("\n3. POST JSON:")
        try:
           resp = await client.post(base_url, json={"key": "val"}, headers=headers)
           print(f"Status: {resp.status_code}")
        except Exception as e:
           print(f"Error: {e}")

        # Check /api/verify/initiate as well
        verify_url = "https://live.meon.co.in/api/verify/initiate"
        print(f"\n4. GET {verify_url} with params:")
        try:
            resp = await client.get(verify_url, params={"test": "1"}, headers=headers)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")
            
if __name__ == "__main__":
    asyncio.run(test_variations())
