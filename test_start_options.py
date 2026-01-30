
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def check_options_start():
    url = "https://live.meon.co.in/api/kyc/start"
    api_key = os.getenv('MEON_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"Checking OPTIONS for {url}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check OPTIONS
        try:
            response = await client.options(url, headers=headers)
            print(f"OPTIONS: {response.status_code}")
            print(f"Allow: {response.headers.get('Allow')}")
        except Exception as e:
            print(f"OPTIONS Error: {e}")
            
        # Check other methods
        methods = ["PUT", "PATCH", "DELETE"]
        for m in methods:
            try:
                response = await client.request(m, url, headers=headers, json={"test": "data"})
                print(f"{m}: {response.status_code}")
                if response.status_code != 405:
                    print(f"Body: {response.text[:200]}")
            except Exception as e:
                print(f"{m} Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_options_start())
