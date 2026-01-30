
import httpx
import os
import asyncio
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def main():
    endpoints = [
        # Check known endpoint from JS
        "https://digilocker.meon.co.in/digilocker/get_credit",
        
        # Check variations for generate link
        "https://digilocker.meon.co.in/digilocker/generate_link",
        "https://digilocker.meon.co.in/digilocker/initiate",
        "https://digilocker.meon.co.in/digilocker/request",
        
        "https://digilocker.meon.co.in/api/v1/generate_link",
        "https://digilocker.meon.co.in/api/v1/digilocker/generate_link",
        "https://digilocker.meon.co.in/api/generate_link",
        
        "https://digilocker.meon.co.in/generate_link",
        
        # Check if Video KYC is a thing
        "https://video-kyc.meon.co.in/api/v1/kyc/generate_link",
        "https://video-kyc.meon.co.in/kyc/generate_link"
    ]
    
    api_key = os.getenv('MEON_API_KEY')
    print(f"API Key present: {bool(api_key)}")
    
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        for url in endpoints:
            print(f"Testing {url}...")
            try:
                resp = await client.post(
                    url, 
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"test": "data"}
                )
                print(f"Status: {resp.status_code}")
                if resp.status_code != 404:
                    print(f"Response: {resp.text[:200]}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
