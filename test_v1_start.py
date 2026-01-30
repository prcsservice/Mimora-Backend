
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def test_v1_start():
    url = "https://live.meon.co.in/api/v1/kyc/start"
    api_key = os.getenv('MEON_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"Testing {url}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # POST
        try:
            resp = await client.post(url, headers=headers, json={"test": "data"})
            print(f"POST {url}: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
        except Exception as e:
            print(f"POST Error: {e}")
            
        # GET (just in case)
        try:
            resp = await client.get(url, headers=headers)
            print(f"GET {url}: {resp.status_code}")
        except Exception as e:
            print(f"GET Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_v1_start())
