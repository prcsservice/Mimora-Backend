
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv("/home/roshan/Mimora-Backend/app/auth/.env")

async def test_get_params():
    url = "https://live.meon.co.in/api/kyc/start"
    api_key = os.getenv('MEON_API_KEY')
    workflow_id = os.getenv("MEON_WORKFLOW_ID", "default_workflow")
    
    params = {
        "reference_id": "test_ref_12345",
        "redirect_url": "https://google.com",
        "user_email": "test@example.com",
        "user_phone": "9999999999",
        "workflow_id": workflow_id
    }
    
    # Also try snake_case vs camelCase
    params_camel = {
        "referenceId": "test_ref_12345",
        "redirectUrl": "https://google.com",
        "userEmail": "test@example.com",
        "userPhone": "9999999999",
        "workflowId": workflow_id
    }

    print(f"Testing GET {url} with params...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. With params in snake_case and Auth Header
        print("\n1. Snake Case Params + Auth Header:")
        try:
            resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {api_key}"})
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Error: {e}")

        # 2. With params in camelCase + Auth Header
        print("\n2. Camel Case Params + Auth Header:")
        try:
            resp = await client.get(url, params=params_camel, headers={"Authorization": f"Bearer {api_key}"})
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Error: {e}")
            
        # 3. With API Key in params (common pattern)
        print("\n3. API Key in Params:")
        params_with_key = params.copy()
        params_with_key["api_key"] = api_key
        params_with_key["key"] = api_key
        try:
            resp = await client.get(url, params=params_with_key)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:300]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_get_params())
