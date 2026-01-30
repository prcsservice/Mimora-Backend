
import asyncio
import httpx
import os

async def check_methods():
    url = "https://live.meon.co.in/kyc/generate_link"
    api_key = os.getenv('MEON_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    methods = ["GET", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
    
    print(f"Checking methods for {url}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for method in methods:
            try:
                response = await client.request(method, url, headers=headers)
                print(f"{method}: {response.status_code}")
                if response.status_code != 405:
                    print(f"Response ({method}): {response.text[:200]}")
            except Exception as e:
                print(f"{method}: Error - {e}")

if __name__ == "__main__":
    asyncio.run(check_methods())
