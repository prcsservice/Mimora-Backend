
import asyncio
import httpx
import os


async def check_options():
    url = "https://digilocker.meon.co.in/api/v1/generate_link"
    api_key = os.getenv('MEON_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"Checking OPTIONS for {url}...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.options(url, headers=headers)
            print(f"OPTIONS: {response.status_code}")
            print(f"Allow Header: {response.headers.get('Allow')}")
            print(f"Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods')}")
            print(f"Response: {response.text[:500]}")
            
            # Also try POST with different content types just in case
            print("\nTrying POST with application/x-www-form-urlencoded...")
            response = await client.post(url, 
                data={"test": "data"},
                headers={"Authorization": f"Bearer {api_key}"}
            )
            print(f"POST (form): {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_options())
