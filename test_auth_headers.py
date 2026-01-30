
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def test_auth_and_multipart():
    url = "https://live.meon.co.in/api/kyc/start"
    api_key = os.getenv('MEON_API_KEY')
    
    auth_variations = [
        ("Bearer", f"Bearer {api_key}"),
        ("Raw", api_key),
        ("Basic", f"Basic {api_key}"),
        ("Token", f"Token {api_key}"),
        ("None", None)
    ]
    
    custom_headers = [
        {"Authorization": val} if val else {} for _, val in auth_variations
    ]
    custom_headers.append({"x-api-key": api_key})
    custom_headers.append({"apikey": api_key})
    custom_headers.append({"Api-Key": api_key})
    
    print(f"Testing {url} with auth variations...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Test GET with different auth headers
        print("\n=== GET Requests ===")
        for h in custom_headers:
            try:
                resp = await client.get(url, headers=h)
                print(f"Header: {list(h.keys())[0]} -> {resp.status_code}")
                if resp.status_code != 400:
                    print(f"  Body: {resp.text[:200]}")
                elif "invalid request" not in resp.text:
                    print(f"  Body: {resp.text[:200]}")
            except Exception as e:
                print(f"Error: {e}")
                
        # 2. Test POST Multipart
        print("\n=== POST Multipart ===")
        # We need to construct multipart data. httpx handles this with 'files' or 'data'
        # For simple fields, 'data' is enough if not expecting files.
        # But to force multipart, we might need 'files' even if empty or dummy.
        
        data = {
            "reference_id": "ref123",
            "user_email": "test@example.com"
        }
        
        try:
            # clean POST with just data (form-encoded usually, but let's try)
            # httpx defaults to urlencoded if data is dict and no files
            
            # To force multipart without files, usage varies. 
            # Let's try sending a dummy file
            files = {'dummy': ('test.txt', b'content')}
            
            resp = await client.post(url, data=data, files=files, headers={"Authorization": f"Bearer {api_key}"})
            print(f"Multipart with file: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
            
        except Exception as e:
            print(f"Multipart Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth_and_multipart())
