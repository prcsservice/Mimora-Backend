
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def fuzz_path():
    base_url = "https://live.meon.co.in/api/kyc"
    api_key = os.getenv('MEON_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    test_ids = ["5cf238ea-d0bf-4945-a927-146ded2e19d7", "test", "123"]
    
    paths = [
        "/start",
        "/initiate",
        "/generate_link"
    ]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for p in paths:
            # Check basic
            url = f"{base_url}{p}"
            # Check with ID appended
            for tid in test_ids:
                url_id = f"{url}/{tid}"
                print(f"Testing {url_id}")
                try:
                    resp = await client.get(url_id, headers=headers)
                    print(f"GET {url_id} -> {resp.status_code}")
                    if resp.status_code != 404:
                         print(f"Body: {resp.text[:100]}")
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fuzz_path())
