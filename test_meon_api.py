
import asyncio
import os
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def main():
    """
    Test various possible Meon API endpoints to find the correct one
    """
    
    # Try different base URLs
    base_urls = [
        os.getenv('MEON_API_BASE_URL', 'https://live.meon.co.in'),
        'https://api.meon.co.in',
        'https://kyc.meon.co.in/api',
        'https://Meon.in/api'
    ]
    
    # Common endpoints for KYC link generation
    possible_endpoints = [
        "/api/v1/kyc/generate_link",  # Standard guess
        "/kyc/generate_link",         # Simple guess
        "/generate_kyc_link",         # Log showed this failing?
        "/kyc/initiate",
        "/api/kyc/initiate"
    ]
    
    api_key = os.getenv('MEON_API_KEY')
    print(f"API Key found: {bool(api_key)}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for base in base_urls:
            print(f"\n--- Testing base: {base} ---")
            for endpoint in possible_endpoints:
                # Handle double slashes if base ends and endpoint starts with slash
                if base.endswith("/") and endpoint.startswith("/"):
                    url = base + endpoint[1:]
                elif not base.endswith("/") and not endpoint.startswith("/"):
                    url = base + "/" + endpoint
                else:
                    url = base + endpoint
                    
                print(f"Testing URL: {url}")
                try:
                    # Minimal payload
                    payload = {
                        "reference_id": "test_ref_123",
                        "redirect_url": "https://example.com/callback",
                        "user_email": "test@example.com",
                        "user_phone": "9999999999"
                    }
                    
                    response = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json=payload
                    )
                    status = response.status_code
                    print(f"Result: {status}")
                    if status != 404:
                         print(f"!!! SUCCESS OR DIFFERENT ERROR: {status}")
                         print(f"Response: {response.text[:200]}")
                except Exception as e:
                    print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
