
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def test_get_with_body():
    url = "https://live.meon.co.in/api/kyc/start"
    api_key = os.getenv('MEON_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"Testing GET {url} with body...")
    
    payload = {
        "reference_id": "test_ref_123",
        "redirect_url": "https://google.com",
        "user_email": "test@example.com",
        "user_phone": "9999999999"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # httpx .get() doesn't support json kwarg directly in recent versions? 
            # It does via .request()
            resp = await client.request("GET", url, headers=headers, json=payload)
            print(f"GET with JSON: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_get_with_body())
